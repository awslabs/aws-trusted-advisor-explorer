# AWS Trusted Advisor Explorer
AWS Trusted Advisor Explorer is an AWS Solution that automatically provisions the infrastructure necessary to aggregate cost optimization recommendations and actively track cost optimization health across your organization over time. The solution creates a data lake that can be used to create dashboards to visually explore the data. The solution enriches the data with Resource Tags that further enhance the discovery and filtering capabilities. 
 
The solution leverages AWS Trusted Advisor’s Cost Optimization recommendations and AWS Resource Groups Tag Editor data to build a data lake that can be queried using Amazon Athena and visualized using Amazon QuickSight or any other visualization platform. 


## Running unit tests for customization
* Clone the repository, then make the desired code changes
* Next, run unit tests to make sure added customization passes the tests
```
cd ./deployment
chmod +x ./run-unit-tests.sh  \n
./run-unit-tests.sh \n
```

## Building distributable for customization
* Configure the bucket name of your target Amazon S3 distribution bucket
```
export DIST_OUTPUT_BUCKET=my-bucket-name # bucket where customized code will reside
export SOLUTION_NAME=my-solution-name
export VERSION=my-version # version number for the customized code
```
_Note:_ You would have to create an S3 bucket with the prefix 'my-bucket-name-<aws_region>'; aws_region is where you are testing the customized solution. Also, the assets in bucket should be publicly accessible.

* Now build the distributable:
```
chmod +x ./build-s3-dist.sh \n
./build-s3-dist.sh $DIST_OUTPUT_BUCKET $SOLUTION_NAME $VERSION \n
```

* Deploy the distributable to an Amazon S3 bucket in your account. _Note:_ you must have the AWS Command Line Interface installed.
```
aws s3 cp ./dist/ s3://my-bucket-name-<aws_region>/$SOLUTION_NAME/$VERSION/ --recursive --acl bucket-owner-full-control --profile aws-cred-profile-name \n
```

* Get the link of the solution template uploaded to your Amazon S3 bucket.
* Deploy the solution to your account by launching a new AWS CloudFormation stack using the link of the solution template in Amazon S3.

*** 

This solution collects anonymous operational metrics to help AWS improve the quality of features of the solution. For more information, including how to disable this capability, please see the [implementation guide](https://docs.aws.amazon.com/solutions/latest/aws-trusted-advisor-explorer/appendix-g.html).

## File Structure

```
.
├── CHANGELOG.md
├── CODE_OF_CONDUCT.md
├── CONTRIBUTING.md
├── LICENSE.txt
├── NOTICE.txt
├── README.md
├── buildspec.yml                                         [ Solution validation pipeline buildspec ]
├── deployment
│   ├── build-s3-dist.sh                                  [ shell script for packaging distribution assets ]
│   ├── cross-account-member-role.template                [ Supplementary member role creation template ]
│   ├── aws-trusted-advisor-explorer.template             [ Main Solution template ]
│   └── run-unit-tests.sh                                 [ shell script for executing unit tests ] 
└── source
    ├── get-tags-lambda.py
    ├── get-accounts-info-lambda.py
    ├── extract-tag-data-lambda.py
    ├── start-crawler-lambda.py
    ├── create-athena-views-lambda.py
    ├── extract-ta-data-lambda.py
    ├── solution-helper.py
    ├── refresh-ta-check-lambda.py
    ├── get-ta-checks-lambda.py
    ├── verify-ta-check-status-lambda.py

```

***


Copyright 2019 Amazon.com, Inc. or its affiliates. All Rights Reserved.

Licensed under the Apache License Version 2.0 (the "License"). You may not use this file except in compliance with the License. A copy of the License is located at

    http://www.apache.org/licenses/

or in the "license" file accompanying this file. This file is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, express or implied. See the License for the specific language governing permissions and limitations under the License.