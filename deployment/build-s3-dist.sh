#!/bin/bash
#
# This assumes all of the OS-level configuration has been completed and git repo has already been cloned
#
# This script should be run from the repo's deployment directory
# cd deployment
# ./build-s3-dist.sh source-bucket-base-name trademarked-solution-name version-code
#
# Paramenters:
#  - source-bucket-base-name: Name for the S3 bucket location where the template will source the Lambda
#    code from. The template will append '-[region_name]' to this bucket name.
#    For example: ./build-s3-dist.sh solutions my-solution v1.0.0
#    The template will then expect the source code to be located in the solutions-[region_name] bucket
#
#  - trademarked-solution-name: name of the solution for consistency
#
#  - version-code: version of the package

# Check to see if input has been provided:
if [ -z "$1" ] || [ -z "$2" ] || [ -z "$3" ]; then
    echo "Please provide the base source bucket name, trademark approved solution name and version where the lambda code will eventually reside."
    echo "For example: ./build-s3-dist.sh solutions trademarked-solution-name v1.0.0"
    exit 1
fi

deployment_dir="$PWD"
template_dist_dir="$deployment_dir/global-s3-assets"
build_dist_dir="$deployment_dir/regional-s3-assets"
source_dir="$deployment_dir/../source"

echo "------------------------------------------------------------------------------"
echo "[Init] Clean old dist folders"
echo "------------------------------------------------------------------------------"
echo "rm -rf $template_dist_dir"
rm -rf $template_dist_dir
echo "mkdir -p $template_dist_dir"
mkdir -p $template_dist_dir
echo "rm -rf $build_dist_dir"
rm -rf $build_dist_dir
echo "mkdir -p $build_dist_dir"
mkdir -p $build_dist_dir

echo "------------------------------------------------------------------------------"
echo "[Packing] Templates"
echo "------------------------------------------------------------------------------"
# CloudFormation template creation
echo "cp -f $deployment_dir/aws-trusted-advisor-explorer.json $template_dist_dir"
cp -f $deployment_dir/aws-trusted-advisor-explorer.json $template_dist_dir

echo "cp -f $deployment_dir/cross-account-member-role.json $template_dist_dir"
cp -f $deployment_dir/cross-account-member-role.json $template_dist_dir

if [[ "$OSTYPE" == "darwin"* ]]; then
    # Mac OS
    echo "Updating code source bucket in the template with $1"
    replace="s/%%BUCKET_NAME%%/$1/g"
    echo "sed -i '' -e $replace $template_dist_dir/aws-trusted-advisor-explorer.json"
    sed -i '' -e $replace $template_dist_dir/aws-trusted-advisor-explorer.json

    echo "Updating solution name in the template with $2"
    replace="s/%%SOLUTION_NAME%%/$2/g"
    echo "sed -i '' -e $replace $template_dist_dir/aws-trusted-advisor-explorer.json"
    sed -i '' -e $replace $template_dist_dir/aws-trusted-advisor-explorer.json

    echo "Updating version number in the template with $3"
    replace="s/%%VERSION%%/$3/g"
    echo "sed -i '' -e $replace $template_dist_dir/aws-trusted-advisor-explorer.json"
    sed -i '' -e $replace $template_dist_dir/aws-trusted-advisor-explorer.json

else
    # Other linux
    echo "Updating code source bucket in the template with $1"
    replace="s/%%BUCKET_NAME%%/$1/g"
    echo "sed -i -e $replace $template_dist_dir/aws-trusted-advisor-explorer.json"
    sed -i -e $replace $template_dist_dir/aws-trusted-advisor-explorer.json

    echo "Updating solution name in the template with $2"
    replace="s/%%SOLUTION_NAME%%/$2/g"
    echo "sed -i -e $replace $template_dist_dir/aws-trusted-advisor-explorer.json"
    sed -i -e $replace $template_dist_dir/aws-trusted-advisor-explorer.json

    echo "Updating version number in the template with $3"
    replace="s/%%VERSION%%/$3/g"
    echo "sed -i -e $replace $template_dist_dir/aws-trusted-advisor-explorer.json"
    sed -i -e $replace $template_dist_dir/aws-trusted-advisor-explorer.json

fi

# rename .json to .template
echo "mv $template_dist_dir/aws-trusted-advisor-explorer.json $template_dist_dir/aws-trusted-advisor-explorer.template"
mv $template_dist_dir/aws-trusted-advisor-explorer.json $template_dist_dir/aws-trusted-advisor-explorer.template

echo "mv $template_dist_dir/cross-account-member-role.json $template_dist_dir/cross-account-member-role.template"
mv $template_dist_dir/cross-account-member-role.json $template_dist_dir/cross-account-member-role.template

echo "------------------------------------------------------------------------------"
echo "[Packing] Lambda functions and scripts"
echo "------------------------------------------------------------------------------"
# Create zip file for AWS Lambda function
echo "cd $source_dir"
cd $source_dir

echo "zip -q -r9 $build_dist_dir/create-athena-views-lambda.zip . -i create-athena-views-lambda.py"
zip -q -r9 $build_dist_dir/create-athena-views-lambda.zip . -i create-athena-views-lambda.py

echo "zip -q -r9 $build_dist_dir/extract-ta-data-lambda.zip . -i extract-ta-data-lambda.py"
zip -q -r9 $build_dist_dir/extract-ta-data-lambda.zip . -i extract-ta-data-lambda.py

echo "zip -q -r9 $build_dist_dir/ extract-tag-data-lambda.zip  extract-tag-data-lambda.py"
zip -q -r9 $build_dist_dir/extract-tag-data-lambda.zip . -i  extract-tag-data-lambda.py

echo "zip -q -r9 $build_dist_dir/get-accounts-info-lambda.zip . -i get-accounts-info-lambda.py"
zip -q -r9 $build_dist_dir/get-accounts-info-lambda.zip . -i get-accounts-info-lambda.py

echo "zip -q -r9 $build_dist_dir/get-ta-checks-lambda.zip . -i get-ta-checks-lambda.py"
zip -q -r9 $build_dist_dir/get-ta-checks-lambda.zip . -i get-ta-checks-lambda.py

echo "zip -q -r9 $build_dist_dir/get-tags-lambda.zip . -i get-tags-lambda.py"
zip -q -r9 $build_dist_dir/get-tags-lambda.zip . -i get-tags-lambda.py

echo "zip -q -r9 $build_dist_dir/refresh-ta-check-lambda.zip . -i refresh-ta-check-lambda.py"
zip -q -r9 $build_dist_dir/refresh-ta-check-lambda.zip . -i refresh-ta-check-lambda.py

echo "zip -q -r9 $build_dist_dir/start-crawler-lambda.zip . -i start-crawler-lambda.py"
zip -q -r9 $build_dist_dir/start-crawler-lambda.zip . -i start-crawler-lambda.py

echo "zip -q -r9 $build_dist_dir/verify-ta-check-status-lambda.zip . -i verify-ta-check-status-lambda.py"
zip -q -r9 $build_dist_dir/verify-ta-check-status-lambda.zip . -i verify-ta-check-status-lambda.py

echo "zip -q -r9 $build_dist_dir/solution-helper.zip . -i solution-helper.py"
zip -q -r9 $build_dist_dir/solution-helper.zip . -i solution-helper.py


echo "Completed building distribution"
cd $template_dist_dir