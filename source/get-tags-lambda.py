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

import json,boto3,os,logging,re
from botocore.exceptions import ClientError

class AWSTrustedAdvisorExplorerGenericException(Exception): pass

sfn = boto3.client('stepfunctions')

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

def execute_state_machine(sfn_arn, resource_parameters):
    logger.info("Executing State Machine :"+sanitize_string(sfn_arn))
    response = sfn.start_execution(
        stateMachineArn=sfn_arn,
        input=resource_parameters
    )
    return response

def describe_regions():
    logger.info("Getting a list of AWS Regions")
    ec2 = boto3.client('ec2',region_name='us-east-1')
    response = ec2.describe_regions()
    regions=[]
    for region in response['Regions']:
        regions.append(region['RegionName'])
    logger.info("Got " + str(len(regions)) + " AWS Regions")
    return regions
        
def get_Mappings(accountId, accountName,accountEmail,date,dateTime,regions):
    logger.info("Generate an Input list of JSON objects that will be passed to the StateMachine")
    resourceTypes = list(os.environ[("ResourceTypes")].split(","))
    finalMap={}
    finalMap['resources'] = []    
    for resourceType in resourceTypes:
        for region in regions:
            finalMap['resources'].append({"ResourceType": resourceType, 
                                        "Region": region, 
                                        "AccountId": accountId, 
                                        "AccountName": accountName, 
                                        "AccountEmail": accountEmail,
                                        "Date": date,
                                        "DateTime": dateTime})
            logger.info(sanitize_json({"ResourceType": resourceType, 
                                        "Region": region, 
                                        "AccountId": accountId, 
                                        "AccountName": accountName, 
                                        "AccountEmail": accountEmail,
                                        "Date": date,
                                        "DateTime": dateTime}))
    return finalMap

def lambda_handler(event, context):
    try:
        logger.info(sanitize_json(event))
        regions = describe_regions()
        finalMap = get_Mappings(event['AccountId'],event['AccountName'],event['AccountEmail'],
                                    event['Date'],event['DateTime'],regions) 
        resource_parameters = finalMap['resources']      
        sfn_execution_ret = execute_state_machine(os.environ['TAG_DATA_EXTRACT_SFN_ARN'], 
                                json.dumps(resource_parameters))
        return {
            'statusCode': 
                sfn_execution_ret['ResponseMetadata']['HTTPStatusCode'],
            'body': sfn_execution_ret['executionArn']
        }
    except ClientError as e:
        e=sanitize_string(e)
        logger.error("Unexpected client error %s" % e)
        raise AWSTrustedAdvisorExplorerGenericException(e)
    except Exception as f:
        f=sanitize_string(f)
        logger.error("Unexpected exception: %s" % f)
        raise AWSTrustedAdvisorExplorerGenericException(f)