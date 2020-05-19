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

import boto3,json,logging,os,re
from datetime import date
from botocore.exceptions import ClientError

class AWSTrustedAdvisorExplorerGenericException(Exception): pass

athenaClient=boto3.client("athena")
glueClient = boto3.client('glue')

#Logger block
logger = logging.getLogger()
if "LOG_LEVEL" in os.environ:
    numeric_level = getattr(logging, os.environ['LOG_LEVEL'].upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError('Invalid log level %s' % loglevel)
    logger.setLevel(level=numeric_level)
    
# --- helper functions ---
def sanitize_string(x):
    y = str(x)
    if os.environ['MASK_PII'].lower() == 'true':
        pattern=re.compile('\d{12}')
        y = re.sub(pattern,lambda match: ((match.group()[1])+'XXXXXXX'+(match.group()[-4:])), y)
    return y
 
def athenaQuery(athenaDb,outputLocation,queryString,workGroupName):
    logger.info('Variables passed to athenaQuery(): ' + athenaDb+','+outputLocation+','+queryString)
    startQueryResponse = athenaClient.start_query_execution(
        QueryString=queryString,
        QueryExecutionContext={
            'Database': athenaDb
        },
        ResultConfiguration={
            'OutputLocation': outputLocation,
            'EncryptionConfiguration': {
                        'EncryptionOption': 'SSE_S3'
                    }            
        },
        WorkGroup=workGroupName
    )
    logger.info("startQueryResponse= " +json.dumps(startQueryResponse))
    return

def checkIfTagsTableExistInDB(athenaDb):
  logger.info('Variables passed to checkIfTagsTableExistInDB(): ' + athenaDb)
  try:
    response = glueClient.get_table(DatabaseName=athenaDb,Name='tags')
    logger.info('get_table response: ' + str(response))
    return "PRESENT"
  except glueClient.exceptions.EntityNotFoundException:
    return "NULL"
  except ClientError as e:
    e = sanitize_string(e)
    logger.error("Unexpected client error %s" % e)
    raise AWSTrustedAdvisorExplorerGenericException(e)
  except Exception as f:
    f = sanitize_string(f)
    logger.error("Unexpected exception: %s" % f)
    raise AWSTrustedAdvisorExplorerGenericException(f)


def lambda_handler(event, context):
    logger.info('lambda_handler() Event : ' + json.dumps(event))
    try:
        workGroupName=os.environ['AthenaWorkGroup']
        status=checkIfTagsTableExistInDB(os.environ['AthenaDb'])
        logger.info('Tags Table Status: ' + json.dumps(status))
        #View Queries
        Query={}
        
        Query['Query_qch7dwoux1']='''CREATE
            OR REPLACE VIEW LowUtilizationAmazonEC2Instances_view AS
    SELECT "check_qch7dwoux1".* , 
             "date_parse"("substr"("check_qch7dwoux1"."datetime", 1, 19), '%Y-%m-%d %T') "date_time",
             CAST("substr"("check_qch7dwoux1"."14-day average cpu utilization", 1, 3) AS decimal(10, 4)) "average_cpu_utilization_14_days" , 
             CAST("substr"("check_qch7dwoux1"."14-day average network i/o", 1, 4) AS decimal(10, 4)) "average_network_i/o_utilization_14 days" , 
             CAST("rtrim"("replace"("substr"("check_qch7dwoux1"."estimated monthly savings", 2), '$')) AS decimal(18,2)) "estimated_monthly_savings" 
             %Insert_Tags_Here% ''' + ('''FROM (check_qch7dwoux1 LEFT JOIN tags
        ON (("check_qch7dwoux1"."instance id" = "tags"."resourceid")
            AND ("check_qch7dwoux1"."datetime" = "tags"."datetime")))''' if (os.environ[("Tags")].strip() != '' and status == 'PRESENT') else "FROM \"check_qch7dwoux1\"")
            
        Query['Query_davu99dc4c']='''CREATE OR REPLACE VIEW UnderutilizedAmazonEBSVolumes_view AS 
    SELECT
      "check_davu99dc4c".*,
      "date_parse"("substr"("check_davu99dc4c"."datetime", 1, 19), '%Y-%m-%d %T') "date_time"
    , CAST("rtrim"("replace"("substr"("check_davu99dc4c"."monthly storage cost", 2),'$')) AS decimal(18,2)) "Monthly_Storage_Cost"
     %Insert_Tags_Here% ''' + ('''FROM (check_davu99dc4c LEFT JOIN tags
        ON (("check_davu99dc4c"."volume id" = "tags"."resourceid")
            AND ("check_davu99dc4c"."datetime" = "tags"."datetime")))''' if (os.environ[("Tags")].strip() != '' and status == 'PRESENT') else "FROM \"check_davu99dc4c\"")
        
        Query['Query_hjlmh88um8']='''CREATE OR REPLACE VIEW IdleLoadBalancers_view AS
    SELECT "check_hjlmh88um8".* ,
             "date_parse"("substr"("check_hjlmh88um8"."datetime", 1, 19), '%Y-%m-%d %T') "date_time",
             CAST("rtrim"("replace"("substr"("check_hjlmh88um8"."estimated monthly savings",2),'$')) AS decimal(18,2)) "estimated_monthly_savings" 
             %Insert_Tags_Here% ''' +('''FROM (check_hjlmh88um8 LEFT JOIN tags
        ON (("check_hjlmh88um8"."load balancer name" = "tags"."resourceid")
            AND ("check_hjlmh88um8"."datetime" = "tags"."datetime")))''' if (os.environ[("Tags")].strip() != '' and status == 'PRESENT') else "FROM \"check_hjlmh88um8\"")


        Query['Query_ti39halfu8']='''CREATE OR REPLACE VIEW AmazonRDSIdleDBInstances_view AS
    SELECT "check_ti39halfu8".* ,
             "date_parse"("substr"("check_ti39halfu8"."datetime", 1, 19), '%Y-%m-%d %T') "date_time",
             CAST("rtrim"("replace"("replace"("check_ti39halfu8"."estimated monthly savings ON demand",'$'),'"')) AS decimal(10,2)) "estimated_monthly_savings"
             %Insert_Tags_Here% ''' +('''FROM (check_ti39halfu8 LEFT JOIN tags
        ON (("check_ti39halfu8"."db instance name" = "tags"."resourceid")
            AND ("check_ti39halfu8"."datetime" = "tags"."datetime")))''' if (os.environ[("Tags")].strip() != '' and status == 'PRESENT') else "FROM \"check_ti39halfu8\"") 
            
        Query['Query_g31sq1e9u']='''CREATE OR REPLACE VIEW UnderutilizedAmazonRedshiftClusters_view AS
    SELECT "check_g31sq1e9u".*,
           "date_parse"("substr"("check_g31sq1e9u"."datetime", 1, 19), '%Y-%m-%d %T') "date_time" 
            %Insert_Tags_Here% ''' +('''FROM (check_g31sq1e9u LEFT JOIN tags
        ON (("check_g31sq1e9u"."cluster" = "tags"."resourceid")
            AND ("check_g31sq1e9u"."datetime" = "tags"."datetime")))''' if (os.environ[("Tags")].strip() != '' and status == 'PRESENT') else "FROM \"check_g31sq1e9u\"")
        
        Query['Query_1e93e4c0b5']='''CREATE OR REPLACE VIEW EC2ReservedInstanceLeaseExpiration_view AS
    SELECT "check_1e93e4c0b5".*,
             "date_parse"("substr"("check_1e93e4c0b5"."datetime", 1, 19), '%Y-%m-%d %T') "date_time",
             CAST("rtrim"("replace"("substr"("check_1e93e4c0b5"."current monthly cost",2),'$')) AS decimal(18,2)) "current_monthly_cost", 
             CAST("rtrim"("replace"("substr"("check_1e93e4c0b5"."estimated monthly savings", 2),'$')) AS decimal(18,2)) "estimated_monthly_savings",
             "date_parse"("substr"("replace"("expiration date", 'T', ' '), 1, 19), '%Y-%m-%d %T') "expiration_date"
    FROM "check_1e93e4c0b5"'''

        Query['Query_51fc20e7i2']='''CREATE OR REPLACE VIEW Route53LatencyResourceRecordSets_view AS
    SELECT "check_51fc20e7i2".*,
     "date_parse"("substr"("check_51fc20e7i2"."datetime", 1, 19), '%Y-%m-%d %T') "date_time" 
    %Insert_Tags_Here% ''' +('''FROM ("check_51fc20e7i2"
    LEFT JOIN tags
        ON (("check_51fc20e7i2"."hosted zone name" = "tags"."resourceid")
            AND ("check_51fc20e7i2"."datetime" = "tags"."datetime")))''' if (os.environ[("Tags")].strip() != '' and status == 'PRESENT') else "FROM \"check_51fc20e7i2\"")
        
        Query['Query_summary']='''CREATE OR REPLACE VIEW summary_view AS 
    SELECT summary.*,
     "date_parse"("substr"("summary"."datetime", 1, 19), '%Y-%m-%d %T') "date_time"
    , ((1 - (CAST("resourcesflagged" AS decimal(10,2)) / CAST("replace"(CAST("resourcesprocessed" AS varchar), '0', '1') AS decimal(10,2)))) * 100) "optimizationPercent"
    , ((1 - ((CAST("resourcesflagged" AS decimal(10,2)) - (CAST("resourcesignored" AS decimal(10,2)) + CAST("resourcessuppressed" AS decimal(10,2)))) / CAST("replace"(CAST("resourcesprocessed" AS varchar), '0', '1') AS decimal(10,2)))) * 100) "trueoptimizationPercent"
    FROM summary'''

        Query['Query_z4aubrnsmz']='''CREATE OR REPLACE VIEW UnassociatedElasticIPAddresses_view AS SELECT "check_z4aubrnsmz".*, "date_parse"("substr"("check_z4aubrnsmz"."datetime", 1, 19), '%Y-%m-%d %T') "date_time" FROM "check_z4aubrnsmz"'''

        Query['Query_cx3c2r1chu']='''CREATE OR REPLACE VIEW EC2ReservedInstancesOptimization_view AS
    SELECT "check_cx3c2r1chu".*,
            "date_parse"("substr"("check_cx3c2r1chu"."datetime", 1, 19), '%Y-%m-%d %T') "date_time",
             CAST("rtrim"("replace"("substr"("check_cx3c2r1chu"."estimated savings with recommendation monthly",2),'$')) AS decimal(18,2)) "estimated_savings_with_recommendation_monthly",
             CAST("rtrim"("replace"("substr"("check_cx3c2r1chu"."upfront cost of ris", 2),'$')) AS decimal(18,2)) "upfront_cost_of_ris",
             CAST("rtrim"("replace"("substr"("check_cx3c2r1chu"."estimated cost of ris monthly", 2),'$')) AS decimal(18,2)) "estimated_cost_of_ris_monthly",
             CAST("rtrim"("replace"("substr"("check_cx3c2r1chu"."estimated on-demand cost post recommended ri purchase monthly",2),'$')) AS decimal(18,2)) "estimated_on-demand_cost_post_recommended_ri_purchase_monthly"
    FROM "check_cx3c2r1chu"'''
        
        checks=["Query_1e93e4c0b5","Query_51fc20e7i2","Query_davu99dc4c","Query_g31sq1e9u","Query_qch7dwoux1","Query_ti39halfu8","Query_z4aubrnsmz","Query_hjlmh88um8","Query_summary"]
        logger.info("Cost Optimization Trusted Advisor Checks:" +str(checks))
        tagsString=''
        tags=[tag.strip() for tag in os.environ[("Tags")].strip().split(",")]
        logger.info("Tags:" +str(tags))
        if os.environ[("Tags")].strip() != '' and status == 'PRESENT':
            for tag in tags:
                tagsString+=',\"tags\".\"'+tag+'\"'
        for checkId in checks:
            outputLocation='s3://'+os.environ['AthenaOutput']+'/AthenaOutputs/'+str(date.today().year)+'/'+str(date.today().month)+'/'+str(date.today().day)+'/'+checkId+'/'
            athenaQuery(os.environ['AthenaDb'],outputLocation,Query[checkId].replace("%Insert_Tags_Here%",tagsString),workGroupName)
    except ClientError as e:
        e = sanitize_string(e)
        logger.error("Unexpected client error %s" % e)
        raise AWSTrustedAdvisorExplorerGenericException(e)
    except Exception as f:
        f = sanitize_string(f)
        logger.error("Unexpected exception: %s" % f)
        raise AWSTrustedAdvisorExplorerGenericException(f)