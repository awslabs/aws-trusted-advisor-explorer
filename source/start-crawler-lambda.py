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

import boto3,logging,os,re
from botocore.exceptions import ClientError

class AWSTrustedAdvisorExplorerGenericException(Exception): pass

glueClient=boto3.client('glue')

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
            if 'account' in k:
                d[k] = sanitize_string(v)
            if 'accountid' in k:
                d[k] = sanitize_string(v)
    return d

def lambda_handler(event,context):
    logger.info(sanitize_json(event))
    try:
        response=glueClient.start_crawler(Name=os.environ['CrawlerName'])
        return response
    except ClientError as e:
        e = sanitize_string(e)
        logger.error("Unexpected client error %s" % e)
        raise AWSTrustedAdvisorExplorerGenericException(e)
    except Exception as f:
        f = sanitize_string(f)
        logger.error("Unexpected exception: %s" % f)
        raise AWSTrustedAdvisorExplorerGenericException(f)