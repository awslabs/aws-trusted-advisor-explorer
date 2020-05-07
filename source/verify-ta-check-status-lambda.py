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

import json,re,boto3,logging,os
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

def verify_trusted_advisor_check_status(supportClient,checkId):
    logger.info("Verify status of Check:"+checkId)
    response = supportClient.describe_trusted_advisor_check_refresh_statuses(
        checkIds=[checkId]
    )
    logger.info(sanitize_json(response))
    return response
    
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
        logger.info("Assume role in child account")
        roleCredentials=assumeRole(event['AccountId'])       
        logger.info("Create boto3 support client using the temporary credentials")
        supportClient=boto3.client("support",region_name="us-east-1",
            aws_access_key_id = roleCredentials['Credentials']['AccessKeyId'],
            aws_secret_access_key = 
                roleCredentials['Credentials']['SecretAccessKey'],
            aws_session_token=roleCredentials['Credentials']['SessionToken'])
        response = verify_trusted_advisor_check_status(supportClient, 
                    event['CheckId']) 
        logger.info("Append the Refresh Status '"+response['statuses'][0]['status']+"' to response." +
            " This will be consumed by downstream Lambda")
        event["RefreshStatus"] = response['statuses'][0]['status']
        logger.info("Refresh for Check "+event['CheckId']+" Returned Refresh Wait Time in Seconds:"+ str((response['statuses'][0]['millisUntilNextRefreshable'])/1000))
        logger.info("Rounding Wait Time to:"+str(round((response['statuses'][0]['millisUntilNextRefreshable'])/1000)))
        if round((response['statuses'][0]['millisUntilNextRefreshable'])/1000) <= 3600:
            event['WaitTimeInSec']= round((response['statuses'][0]['millisUntilNextRefreshable'])/1000)
        else:
            logger.info("Skipping Refresh for Check "+event['CheckId']+" as wait time"+ str(round((response['statuses'][0]['millisUntilNextRefreshable'])/1000))+ "is greater than 1 hour")
            event['WaitTimeInSec']= 0
        return event
    except ClientError as e:
        e = sanitize_string(e)
        logger.error("Unexpected client error %s" % e)
        raise AWSTrustedAdvisorExplorerGenericException(e)
    except Exception as f:
        f = sanitize_string(f)
        logger.error("Unexpected exception: %s" % f)
        raise AWSTrustedAdvisorExplorerGenericException(f)