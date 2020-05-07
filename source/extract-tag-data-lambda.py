######################################################################################################################
#  Copyright 2019 Amazon.com, Inc. or its affiliates. All Rights Reserved.                                           #
#                                                                                                                    #
#  Licensed under the Apache License Version 2.0 (the "License"). You may not use this file except in compliance     #
#  with the License. A copy of the License is located at                                                             #
#                                                                                                                    #
#      http://www.apache.org/licenses/                                                                               #
#                                                                                                                    #
#  or in the "license" file accompanying this file. This file is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES #
#  OR CONDITIONS OF ANY KIND, express or implied. See the License for the specific language governing permissions    #
#  and limitations under the License.                                                                                #
######################################################################################################################

import boto3,csv,os,re,logging
from datetime import datetime,date
from subprocess import call
from botocore.exceptions import ClientError

class AWSTrustedAdvisorExplorerGenericException(Exception): pass

#Logger block
logger = logging.getLogger()
if "LOG_LEVEL" in os.environ:
    numeric_level = getattr(logging, os.environ['LOG_LEVEL'].upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError('Invalid log level %s' % loglevel)
    logger.setLevel(level=numeric_level)

def sanitize_string(x):
    y = str(x)
    if os.environ['MASK_PII'].lower() == 'true':
        pattern=re.compile('\d{12}')
        y = re.sub(pattern,lambda match: ((match.group()[1])+'XXXXXXX'+(match.group()[-4:])), y)
    return y

def sanitize_json(x):
    d = x.copy()
    if os.environ['MASK_PII'].lower() == 'true':
        for k, v in d.items():
            if 'AccountId' in k:
                d[k] = sanitize_string(v)
            if 'AccountName' in k:
                d[k] = v[:3]+'-MASKED-'+v[-3:]
            if 'AccountEmail' in k:
                d[k] = v[:3]+'-MASKED-'+v[-3:]
    return d

def getResourceId(Arn):
    #RegEx Pattern
    pattern1=re.compile('.*\/(.*$)')
    pattern2=re.compile('.*\:(.*$)')
    match=pattern1.match(Arn)
    if match == None:
        match=pattern2.match(Arn)
        if match == None:
            return ''
    return match.group(1)

#Get Tag Information & Resource List
def getTagInfo(accountId,region,resourceType,customerKeys,Date,dateTime,accountName,accountEmail):
    tagInfo={}
    #Assume a role and generate a Client
    roleCredentials=assumeRole(accountId)
    #Construct Client
    tagClient=boto3.client("resourcegroupstaggingapi",
        region_name=region,
        aws_access_key_id=roleCredentials['Credentials']['AccessKeyId'],
        aws_secret_access_key=roleCredentials['Credentials']['SecretAccessKey'],
        aws_session_token=roleCredentials['Credentials']['SessionToken'])
    paginator = tagClient.get_paginator('get_resources')
    for customerKey in customerKeys:
        page_Iterator = paginator.paginate(ResourceTypeFilters=[resourceType],TagFilters=[{'Key': customerKey}])
        for page in page_Iterator:
            for resource in page['ResourceTagMappingList']:
                for tag in resource['Tags']:
                    if tag['Key'] == customerKey:
                        if resource['ResourceARN'] not in tagInfo.keys():
                            tagInfo[resource['ResourceARN']]={}
                        tagInfo[resource['ResourceARN']][customerKey]=tag['Value']
                        tagInfo[resource['ResourceARN']]['ResourceArn']=resource['ResourceARN']
                        tagInfo[resource['ResourceARN']]['ResourceId']=getResourceId(resource['ResourceARN'])
                        tagInfo[resource['ResourceARN']]['ResourceType']=resourceType
                        tagInfo[resource['ResourceARN']]['RegionName']=region
                        tagInfo[resource['ResourceARN']]['Date']=Date
                        tagInfo[resource['ResourceARN']]['DateTime']=dateTime
                        tagInfo[resource['ResourceARN']]['AccountId']=accountId
                        tagInfo[resource['ResourceARN']]['AccountName']=accountName
                        tagInfo[resource['ResourceARN']]['AccountEmail']=accountEmail
    return tagInfo

def write2csv(tagInfo,fileName,file_Header):
    logger.info('Variables passed to write2csv(): Data,' + 
        sanitize_string(fileName) +','+str(file_Header))
    with open("/tmp/"+fileName, 'w') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=file_Header)
        writer.writeheader()
        for key in tagInfo:
            logger.info(sanitize_json(tagInfo[key]))
            writer.writerow(tagInfo[key])
    logger.info('Number of rows in file '+ sanitize_string(fileName) +
        '(including header): ' + str(len(tagInfo.keys())))
    csvfile.close()
    logger.info('Size of file "' + sanitize_string(fileName) + 
        '": '+str(os.stat("/tmp/"+fileName).st_size)+" bytes")
    return 

#Write to S3
def writeToS3(fileName,s3Path):
    logger.info('Variables passed to writeToS3(): '+sanitize_string(fileName)+','+s3Path)
    #required variables
    bucketName=os.environ['S3BucketName']
    s3Client = boto3.resource('s3')
    s3Client.meta.client.upload_file('/tmp/'+fileName, bucketName, s3Path+fileName,ExtraArgs={'ACL': 'bucket-owner-full-control'})
    return

#Assume Role in Child Account
def assumeRole(accountId):
    logger.info('Variables passed to assumeRole(): '+sanitize_string(accountId))
    roleArn="arn:aws:iam::"+str(accountId)+":role/"+os.environ['IAMRoleName']
    #STS assume role call
    stsClient = boto3.client('sts')
    roleCredentials = stsClient.assume_role(RoleArn=roleArn, RoleSessionName="AWSTrustedAdvisorExplorerAssumeRole")
    return roleCredentials

def lambda_handler(event, context):
    logger.info(sanitize_json(event))
    if os.environ[("CustomerKeys")].strip() !='':
        try:
            file_Header=['Date','DateTime','AccountId','AccountName','AccountEmail',
                'RegionName','ResourceType','ResourceArn','ResourceId']
            customerKeys=[tag.strip() for tag in os.environ[("CustomerKeys")].strip().split(",")]
            logger.info("Tags: "+str(customerKeys))
            file_Header.extend(customerKeys)            
            tagInfo=getTagInfo(str(event['AccountId']),event['Region'],event['ResourceType'],customerKeys,event['Date'],event['DateTime'],event['AccountName'],event['AccountEmail'])        
            if len(tagInfo.keys()) > 0:
                #Resource File Name
                resourceFilename=(str(event['ResourceType'])+"_"+str(event['AccountId'])+"_"+event['Region']+"_"+str(event['Date'])+"_"+str(datetime.utcnow().strftime("%H-%M-%S"))+'.csv')
                #Write the Values into a csv file
                write2csv(tagInfo,resourceFilename,file_Header)
                #Construct S3 Path
                resourceFilePath='Tags/'+str(event['ResourceType'])+'/'+str(date.today().year)+'/'+str(date.today().month)+'/'+str(date.today().day)+'/'
                #Copy file to S3
                writeToS3(resourceFilename,resourceFilePath)
                logger.info("Clean /tmp/")
                call('rm -rf /tmp/*', shell=True)      
        except ClientError as e:
            e = sanitize_string(e)
            logger.error("Unexpected client error %s" % e)
            raise AWSTrustedAdvisorExplorerGenericException(e)
        except Exception as f:
            f = sanitize_string(f)
            logger.error("Unexpected exception: %s" % f)
            raise AWSTrustedAdvisorExplorerGenericException(f)