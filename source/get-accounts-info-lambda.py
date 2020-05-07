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

"""
getAccountsFromOrganizations
Input: 
if the FILE_OVERRIDE environment variable is set to true, then the BUCKET_NAME 
and OBJECT_NAME serve as inputs. if FILE_OVERRIDE is set to false,then there are 
no inputs to this lambda function

Output:
Status and Step function execution ARNs for the following.
1> TA data extract state machine
2> Tag data extract state machine

Description:
This function creates the input parameters needed to execute the step function 
state machine: MapOrganizations and TagMapOrganizations. The input is either 
from organizations or a user defined csv. The step functions Map contruct is 
used to create parallel branches - one per account. 
"""
import json,re,boto3,os,csv,logging,datetime
from botocore.exceptions import ClientError
import urllib.request as request

class AWSTrustedAdvisorExplorerGenericException(Exception): pass

orgs = boto3.client('organizations',region_name='us-east-1')
sfn = boto3.client('stepfunctions')
s3 = boto3.client('s3')

logger = logging.getLogger()
if "LOG_LEVEL" in os.environ:
    numeric_level = getattr(logging, os.environ['LOG_LEVEL'].upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError('Invalid log level: %s' % loglevel)
    logger.setLevel(level=numeric_level)

# Send anonymous metric function
def send_anonymous_metric():
    now = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
    metric_url = 'https://metrics.awssolutionsbuilder.com/generic'
    response_body = json.dumps({
        "Solution": "SO0082",
        "UUID": os.environ['UUID'],
        "TimeStamp": now,
        "Data": {
            "SolutionRunTime": now,
            "Region": os.environ['AWS_REGION'],
            "Version": os.environ['Version']
        }
    })
    logger.info('Metric Body: {}'.format(response_body))

    try:
        data = response_body.encode('utf-8')
        req = request.Request(metric_url, data=data)
        req.add_header('Content-Type', 'application/json')
        req.add_header('Content-Length', len(response_body))
        response = request.urlopen(req)

        logger.info('Status code: {}'.format(response.getcode()))
        logger.info('Status message: {}'.format(response.msg))
    except Exception as e:
        logger.error('Error occurred while sending metric: {}'.format(json.dumps(response_body)))
        logger.error('Error: {}'.format(e))     

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
        input=resource_parameters)
    return response

def list_accounts_from_organizations():
    logger.info("Extracting Accounts via AWS Organizations")
    paginator = orgs.get_paginator('list_accounts')
    page_iterator = paginator.paginate()
    accounts = {}
    accounts["accounts"] = []
    todaysDate = datetime.datetime.utcnow().strftime("%m-%d-%Y")
    todaysDateTime = datetime.datetime.utcnow().strftime('%Y-%m-%d %T')
    for page in page_iterator:
        for x in page['Accounts']:
            if x['Status'] == 'ACTIVE':
                accounts["accounts"].append({"AccountId": x['Id'], 
                                             "AccountName": x['Name'], 
                                             "AccountEmail": x['Email'],
                                             "Date": todaysDate,
                                             "DateTime": todaysDateTime})
                logger.info(sanitize_json({"AccountId": x['Id'], 
                                             "AccountName": x['Name'], 
                                             "AccountEmail": x['Email'],
                                             "Date": todaysDate,
                                             "DateTime": todaysDateTime}))
    return accounts

def list_accounts_from_file():
    logger.info("Extracting Accounts via File Input:" + os.environ['BUCKET_NAME'] +','+os.environ['OBJECT_NAME'])
    accounts = {}
    accounts["accounts"] = []
    file_name = '/tmp/accounts.csv' 
    s3.download_file(os.environ['BUCKET_NAME'], os.environ['OBJECT_NAME'], 
        file_name)    
    with open(file_name) as csvfile:
        readCSV = csv.reader(csvfile, delimiter=',')
        x = 0
        # keep track of the positions, since this is a user defined file
        accountIdPos = 0
        accountNamePos = 0
        accountEmailPos = 0
        todaysDate = datetime.datetime.utcnow().strftime("%m-%d-%Y")
        todaysDateTime = datetime.datetime.utcnow().strftime('%Y-%m-%d %T')
        for row in readCSV:
            if len(row) == 3:
                # read in the headers
                if x == 0:
                    for y in range(len(row)):
                        if row[y].lower() == 'accountid':
                            accountIdPos = y
                        if row[y].lower() == 'accountname':
                            accountNamePos = y
                        if row[y].lower() == 'accountemail':
                            accountEmailPos = y
                else:
                    accounts["accounts"].append({"AccountId": row[accountIdPos].strip(), 
                                     "AccountName": row[accountNamePos].strip(), 
                                     "AccountEmail": row[accountEmailPos].strip(),
                                     "Date": todaysDate,
                                     "DateTime": todaysDateTime})
                    logger.info(sanitize_json({"AccountId": row[accountIdPos].strip(), 
                                     "AccountName": row[accountNamePos].strip(), 
                                     "AccountEmail": row[accountEmailPos].strip(),
                                     "Date": todaysDate,
                                     "DateTime": todaysDateTime}))
            else:
                logger.error("Input needs to have 3 fields: AccountId," +
                    "AccountName and AccountEmail")
                raise Exception("Insufficient fields in input file")
            x = x + 1
    return accounts 

def lambda_handler(event, context):
    logger.info(json.dumps(event))
    accounts = {}
    try:
        if os.environ['FILE_OVERRIDE'].lower() == 'true':
            accounts = list_accounts_from_file()
        else:
            accounts = list_accounts_from_organizations()            
        resource_parameters = accounts['accounts']     
        logger.info("Batching Accounts by 50 to overcome step-function Input limitation of max  32,768 characters")
        n = 50  
        accountsBatch = [resource_parameters[i * n:(i + 1) * n] for i in range((len(resource_parameters) + n - 1) // n )]        
        response=[]        
        for batch in accountsBatch:
            TA_data_extract_sfn_execution_ret = \
                execute_state_machine(os.environ['EXTRACT_TA_DATA_SFN_ARN'],  
                    json.dumps(batch))
            response.append({
                'statusCode': 
                    TA_data_extract_sfn_execution_ret['ResponseMetadata']
                    ['HTTPStatusCode'],
                'body': json.dumps({"TA_data_extract_sfn_execution_ret": 
                    TA_data_extract_sfn_execution_ret['executionArn']})
                    })
            
            if os.environ[("Tags")].strip() != '':
                tag_data_extract_sfn_execution_ret = \
                    execute_state_machine(os.environ['TAG_DATA_EXTRACT_SFN_ARN'], \
                        json.dumps(batch))
            
                response.append({
                    'statusCode': 
                        tag_data_extract_sfn_execution_ret['ResponseMetadata']
                        ['HTTPStatusCode'],
                    'body': json.dumps({"tag_data_extract_sfn_execution_ret": 
                        tag_data_extract_sfn_execution_ret['executionArn']})})
        if os.environ['AnonymousUsage'].lower() == "yes":
            send_anonymous_metric()        
        return response
    except ClientError as e:
        e = sanitize_string(e)
        logger.error("Unexpected client error %s" % e)
        raise AWSTrustedAdvisorExplorerGenericException(e)
    except Exception as f:
        f = sanitize_string(f)
        logger.error("Unexpected exception: %s" % f)
        raise AWSTrustedAdvisorExplorerGenericException(f)