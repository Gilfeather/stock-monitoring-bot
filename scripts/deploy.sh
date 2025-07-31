#!/bin/bash

# Terraformでデプロイ
set -e

ENVIRONMENT=${1:-dev}

echo "Deploying to environment: $ENVIRONMENT"

# 環境別のtfvarsファイルが存在するかチェック
TFVARS_FILE="environments/$ENVIRONMENT.tfvars"
if [ ! -f "terraform/$TFVARS_FILE" ]; then
    echo "Error: $TFVARS_FILE not found"
    exit 1
fi

# Lambdaパッケージをビルド
./scripts/build.sh

# Terraformでデプロイ
cd terraform
terraform init -backend-config="key=stock-monitoring-bot/$ENVIRONMENT/terraform.tfstate"
terraform workspace select $ENVIRONMENT || terraform workspace new $ENVIRONMENT
terraform plan -var-file="$TFVARS_FILE"
terraform apply -var-file="$TFVARS_FILE" -auto-approve

echo "Deployment completed for environment: $ENVIRONMENT"