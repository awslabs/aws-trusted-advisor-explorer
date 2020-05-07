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

import re,boto3,logging,os
from datetime import date
from botocore.exceptions import ClientError

class AWSTrustedAdvisorExplorerGenericException(Exception): pass

logger = logging.getLogger()
if "LOG_LEVEL" in os.environ:
    numeric_level = getattr(logging, os.environ['LOG_LEVEL'].upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError('Invalid log level: %s' % loglevel)
    logger.setLevel(level=numeric_level) 

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

def sanitize_string(x):
    y = str(x)
    if os.environ['MASK_PII'].lower() == 'true':
        pattern=re.compile('\d{12}')
        y = re.sub(pattern,lambda match: ((match.group()[1])+'XXXXXXX'+(match.group()[-4:])), y)
    return y

def refresh_trusted_advisor_checks(supportClient,checkId):
    logger.info('Refreshing Trusted Advisor Check:'+checkId)
    response = supportClient.refresh_trusted_advisor_check(
        checkId=checkId
    )
    logger.info(sanitize_json(response))
    return response

def checkAssumeRoleFailure(error):
    if "(AccessDenied) when calling the AssumeRole operation" in error:
        pattern=re.compile('.*iam::(\d{12}):.*$')
        match=pattern.match(error)
        logger.info('Assume Role Error for Account:'+match.group(1))
        if match != None:       
            key_name='Logs/AssumeRoleFailure/'+ str(date.today().year)+ '/'+str(date.today().month)+'/'+str(date.today().day)+'/'+str(match.group(1))+'.log'
            client = boto3.client('s3')
            client.put_object(ACL='bucket-owner-full-control',StorageClass='STANDARD',Body=error, Bucket=os.environ['S3BucketName'],Key=key_name)
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
    try:
        logger.info(sanitize_json(event))
        logger.info("Assume Role in child account")
        roleCredentials=assumeRole(event['AccountId'])       
        logger.info("Create boto3 support client using the temporary credentials")
        supportClient=boto3.client("support",region_name="us-east-1",
            aws_access_key_id = roleCredentials['Credentials']['AccessKeyId'],
            aws_secret_access_key = 
                roleCredentials['Credentials']['SecretAccessKey'],
            aws_session_token=roleCredentials['Credentials']['SessionToken'])
        response = refresh_trusted_advisor_checks(
                    supportClient, event['CheckId'])
        logger.info("Append the Refresh Status '"+response['status']['status']+"' to response." +
            " This will be consumed by downstream Lambda")
        event["RefreshStatus"] = response['status']['status']        
        return event
    except ClientError as e:
        checkAssumeRoleFailure(str(e))
        e=sanitize_string(e)
        logger.error("Unexpected client error %s" % e)
        raise AWSTrustedAdvisorExplorerGenericException(e)
    except Exception as f:
        checkAssumeRoleFailure(str(f))
        f=sanitize_string(f)
        logger.error("Unexpected exception: %s" % f)
        raise AWSTrustedAdvisorExplorerGenericException(f)