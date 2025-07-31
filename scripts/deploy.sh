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

# Discord Lambda関数をビルド
./scripts/build_discord_lambda.sh

# Cloudflare Workerをビルド
./scripts/build_cloudflare_worker.sh

# Terraformでデプロイ
cd terraform
terraform init -reconfigure -backend-config="key=stock-monitoring-bot/$ENVIRONMENT/terraform.tfstate"
terraform workspace select $ENVIRONMENT || terraform workspace new $ENVIRONMENT
terraform plan -var-file="$TFVARS_FILE"
terraform apply -var-file="$TFVARS_FILE" -auto-approve

# Go back to root directory
cd ..

# Deploy Cloudflare Worker (if CLOUDFLARE_API_TOKEN is set)
if [ -n "$CLOUDFLARE_API_TOKEN" ]; then
    echo "Deploying Cloudflare Worker..."
    
    # Deploy the worker
    (cd cloudflare-worker && CLOUDFLARE_API_TOKEN="$CLOUDFLARE_API_TOKEN" npx wrangler deploy --name stock-monitoring-bot-discord-webhook-$ENVIRONMENT)
    
    echo "Setting up Cloudflare Worker secrets..."
    
    # Get AWS credentials from Terraform outputs
    AWS_ACCESS_KEY_ID=$(cd terraform && terraform output -raw cloudflare_access_key_id)
    AWS_SECRET_ACCESS_KEY=$(cd terraform && terraform output -raw cloudflare_secret_access_key)
    SQS_QUEUE_URL=$(cd terraform && terraform output -raw sqs_queue_url)
    
    # Get Discord public key from tfvars
    DISCORD_PUBLIC_KEY=$(grep 'discord_public_key' "terraform/$TFVARS_FILE" | cut -d'"' -f2)
    
    # Set secrets using wrangler (we're currently in terraform directory, worker dir is ../cloudflare-worker)
    echo "Setting DISCORD_PUBLIC_KEY..."
    (cd cloudflare-worker && echo $DISCORD_PUBLIC_KEY | CLOUDFLARE_API_TOKEN="$CLOUDFLARE_API_TOKEN" npx wrangler secret put DISCORD_PUBLIC_KEY --name stock-monitoring-bot-discord-webhook-$ENVIRONMENT)
    
    echo "Setting AWS_ACCESS_KEY_ID..."
    (cd cloudflare-worker && echo $AWS_ACCESS_KEY_ID | CLOUDFLARE_API_TOKEN="$CLOUDFLARE_API_TOKEN" npx wrangler secret put AWS_ACCESS_KEY_ID --name stock-monitoring-bot-discord-webhook-$ENVIRONMENT)
    
    echo "Setting AWS_SECRET_ACCESS_KEY..."
    (cd cloudflare-worker && echo $AWS_SECRET_ACCESS_KEY | CLOUDFLARE_API_TOKEN="$CLOUDFLARE_API_TOKEN" npx wrangler secret put AWS_SECRET_ACCESS_KEY --name stock-monitoring-bot-discord-webhook-$ENVIRONMENT)
    
    echo "Setting SQS_QUEUE_URL..."
    (cd cloudflare-worker && echo $SQS_QUEUE_URL | CLOUDFLARE_API_TOKEN="$CLOUDFLARE_API_TOKEN" npx wrangler secret put SQS_QUEUE_URL --name stock-monitoring-bot-discord-webhook-$ENVIRONMENT)
    
    echo "Cloudflare Worker secrets configured successfully"
else
    echo "⚠️  CLOUDFLARE_API_TOKEN not set, skipping Cloudflare Worker deployment"
    echo "   To deploy Cloudflare Worker, run: CLOUDFLARE_API_TOKEN=your_token make deploy-dev"
fi

echo "Deployment completed for environment: $ENVIRONMENT"