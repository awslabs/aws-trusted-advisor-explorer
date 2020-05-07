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

import boto3,csv,os,logging,re
from datetime import date,datetime
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

def sanitize_list(x):
    v = x.copy()
    if os.environ['MASK_PII'].lower() == 'true':
        v[-3]=sanitize_string(v[-3])
        v[-2]=v[-2][:3]+'-MASKED-'+v[-2][-3:]
        v[-1]=v[-1][:3]+'-MASKED-'+v[-1][-3:]
    return v

def write2csv(values,fileName):
    logger.info('Variables passed to writeToCsv(): Data & Filename(' + 
        sanitize_string(fileName) + ')' )
    csv_out = open("/tmp/"+fileName, 'w')
    mywriter = csv.writer(csv_out)
    mywriter.writerows(values)
    logger.info('Number of rows in file '+ sanitize_string(fileName) +
        '(including header): ' + str(len(values)))
    csv_out.close()
    logger.info('Size of file "' + sanitize_string(fileName) + 
        '": '+str(os.stat("/tmp/"+fileName).st_size)+" bytes")
    return os.stat("/tmp/"+fileName).st_size

#Get TA Check Results
def getTACheckResults(checkId,client,language):
    logger.info("Getting Trusted Advisor Results for Check & Language:" +checkId+','+language)
    result = client.describe_trusted_advisor_check_result(checkId=checkId,
        language=language.lower())
    logger.info(result)
    return result

#Write to S3
def writeToS3(fileName,s3Path):
    logger.info('Variables passed to writeToS3(): '+ 
        sanitize_string(fileName)+','+s3Path)
    #required variables
    bucketName=os.environ['S3BucketName']
    s3Client = boto3.resource('s3')
    s3Client.meta.client.upload_file('/tmp/'+fileName, bucketName, 
        s3Path+fileName,ExtraArgs={'ACL': 'bucket-owner-full-control'})
    return fileName

#Assume Role in Child Account
def assumeRole(accountId):
    logger.info('Variables passed to assumeRole(): '+sanitize_string(accountId))
    roleArn="arn:aws:iam::"+str(accountId)+":role/"+os.environ['IAMRoleName']
    #STS assume role call
    stsClient = boto3.client('sts')
    roleCredentials = stsClient.assume_role(RoleArn=roleArn, RoleSessionName="AWSTrustedAdvisorExplorerAssumeRole")
    return roleCredentials
        
#TA Check & Parse
def genericTAParse(client,checkId,accountId,accountName,accountEmail,language,
        Date,dateTime,checkName,category):  
    #Construct File Name (CheckID_AccountID_CheckName_Date_Time.csv)
    resourceFilename=(checkId+"_"+str(accountId)+"_"+str(Date)+"_"+
        str(datetime.utcnow().strftime("%H-%M-%S"))+'.csv')
    summaryFilename=(checkId+"_"+str(accountId)+"_Summary_"+str(Date)+
        "_"+str(datetime.utcnow().strftime("%H-%M-%S"))+'.csv')    
    fileDetails = [{"SummaryFileName":summaryFilename,
                    "SummaryFileSize": 0}, 
                    {"DetailsFileName":resourceFilename,
                    "DetailsFileSize": 0}]
    #Construct S3 Path
    resourceFilePath='TA-Reports/'+category+'/check_'+checkId+'/'+ \
        str(date.today().year)+'/'+str(date.today().month)+'/'+ \
        str(date.today().day)+'/'
    summaryFilePath='TA-Reports/'+category+'/Summary/'+str(date.today().year)+ \
        '/'+str(date.today().month)+'/'+str(date.today().day)+'/'
    #TA Check Module
    result=getTACheckResults(checkId,client,language)
    try:
        summaryFileHeader=list(os.environ[("Header_Summary")].split(","))
        logger.info("Summary Header from environment variables:"+str(summaryFileHeader))
        resourceFileHeader=list(os.environ[("Header_"+checkId)].split(","))
        logger.info(checkId+" Check Header from environment variables:"+str(resourceFileHeader))
        resourceFileSchema=list(os.environ[("Schema_"+checkId)].split(","))
        logger.info(checkId+" Check Schema from environment variables:"+str(resourceFileSchema))
    except Exception as e:
        logger.error("Unable to find env variable : %s" %e)
        raise Exception("Unable to find env variable %s" % e)    
    logger.info("Trusted Advisor Summary Execution Block")
    summaryFileHeader.extend(["AccountId","AccountName","AccountEmail"])
    summaryFileHeader.insert(0,"CheckName") 
    summaryFileHeader.insert(0,"DateTime")
    summaryFileHeader.insert(0,"Date")
    summaryFileRows=[summaryFileHeader]
    summaryFileRow=[Date,dateTime,checkName,result['result']['checkId'],
        result['result']['status'],
        result['result']['resourcesSummary']['resourcesProcessed'],
        result['result']['resourcesSummary']['resourcesFlagged'],
        result['result']['resourcesSummary']['resourcesIgnored'],
        result['result']['resourcesSummary']['resourcesSuppressed']]
    if "costOptimizing" in result['result']['categorySpecificSummary'].keys():
        summaryFileRow.extend(
            [result['result']['categorySpecificSummary']['costOptimizing']\
            ['estimatedMonthlySavings'],result['result']\
            ['categorySpecificSummary']['costOptimizing']\
            ['estimatedPercentMonthlySavings'],
            str(accountId),accountName,accountEmail])
    else:
        summaryFileRow.extend([0,0,str(accountId),accountName,accountEmail])
    logger.info(sanitize_list(summaryFileRow))
    summaryFileRows.append(summaryFileRow)

    
    #Write the Summary Values into a csv file & Copy file to S3
    if len(summaryFileRows) > 1:
        fileDetails[0]['SummaryFileSize'] = write2csv(summaryFileRows,summaryFilename)
        writeToS3(summaryFilename,summaryFilePath)
    
    logger.info("Trusted Advisor Results Execution Block")
    #TA Flagged Resources Execution
    resourceFileHeader.extend(["AccountId","AccountName","AccountEmail"])
    resourceFileHeader.insert(0,"CheckName")
    resourceFileHeader.insert(0,"DateTime")
    resourceFileHeader.insert(0,"Date")
    resourceFileRows=[resourceFileHeader]
    for i in range(0,len(result['result']['flaggedResources'])):
        if result['result']['flaggedResources'][i]['status'] == "warning" or \
            result['result']['flaggedResources'][i]['status'] == "error":
            store=result['result']['flaggedResources'][i]
            resourceFileRow=[]
            for key in resourceFileSchema:
                if key.isdigit() == True:
                    if store['metadata'][int(key)] is None:
                        resourceFileRow.append(store['metadata'][int(key)])
                    else:
                        resourceFileRow.append(
                                store['metadata'][int(key)].replace(",",""))
                else:
                    resourceFileRow.append(store[key])
            resourceFileRow.extend([str(accountId),accountName,accountEmail])
            resourceFileRow.insert(0,checkName)
            resourceFileRow.insert(0,dateTime)
            resourceFileRow.insert(0,Date)
            logger.info(sanitize_list(resourceFileRow))
            resourceFileRows.append(resourceFileRow)
    

    #Write the Resource Values into a csv file & Copy file to S3
    if len(resourceFileRows) > 1:
        fileDetails[1]['DetailsFileSize'] = write2csv(resourceFileRows,resourceFilename)
        writeToS3(resourceFilename,resourceFilePath)
    
    logger.info("Clean /tmp/")
    call('rm -rf /tmp/*', shell=True)
     
    return {"status": result['ResponseMetadata']['HTTPStatusCode'],
            "checkId": checkId, "fileDetails": fileDetails}    

def lambda_handler(event, context):
    if ("Header_"+event['CheckId']) in os.environ and ("Schema_"+event['CheckId']) in os.environ:
        try:
            logger.info(sanitize_json(event))
            logger.info("Assume role in child account")
            roleCredentials=assumeRole(event['AccountId'])       
            logger.info("Create boto3 support client using the temporary credentials")
            supportClient=boto3.client("support",region_name="us-east-1",
                aws_access_key_id = roleCredentials['Credentials']['AccessKeyId'],
                aws_secret_access_key = 
                    roleCredentials['Credentials']['SecretAccessKey'],
                aws_session_token=roleCredentials['Credentials']['SessionToken'])        
            result = genericTAParse(supportClient,event['CheckId'],event['AccountId'],
                event['AccountName'],event['AccountEmail'],event['Language'],
                event['Date'],event['DateTime'],event['CheckName'],
                event['Category'])
            logger.info(result)
            return result      
        except ClientError as e:
            e = sanitize_string(e)
            logger.error("Unexpected client error %s" % e)
            raise AWSTrustedAdvisorExplorerGenericException(e)
        except Exception as f:
            f = sanitize_string(f)
            logger.error("Unexpected exception: %s" % f)
            raise AWSTrustedAdvisorExplorerGenericException(f)
    else:
        return "Header_"+event['CheckId']+" not found in env variables; Skipping Check"