#!/bin/bash

# Deploy Cloudflare Worker and configure secrets
set -e

ENVIRONMENT=${1:-dev}
WORKER_NAME="stock-monitoring-bot-discord-webhook-$ENVIRONMENT"

echo "Deploying Cloudflare Worker: $WORKER_NAME"

# Check if CLOUDFLARE_API_TOKEN is set
if [ -z "$CLOUDFLARE_API_TOKEN" ]; then
    echo "Error: CLOUDFLARE_API_TOKEN environment variable is not set"
    exit 1
fi

# Build the worker
./scripts/build_cloudflare_worker.sh

# Deploy the worker using wrangler
cd cloudflare-worker
echo "Deploying worker with wrangler..."
npx wrangler deploy --name "$WORKER_NAME"

# Get Terraform outputs for secrets
cd ../terraform
echo "Getting AWS credentials from Terraform..."

# Check if terraform state exists
if ! terraform show > /dev/null 2>&1; then
    echo "Error: Terraform state not found. Please run 'make deploy-dev' first to create AWS resources."
    exit 1
fi

SQS_QUEUE_URL=$(terraform output -raw sqs_queue_url)
AWS_ACCESS_KEY_ID=$(terraform output -raw cloudflare_access_key_id)
AWS_SECRET_ACCESS_KEY=$(terraform output -raw cloudflare_secret_access_key)

# Get Discord public key from tfvars
DISCORD_PUBLIC_KEY=$(grep 'discord_public_key' "environments/$ENVIRONMENT.tfvars" | cut -d'"' -f2)

echo "Setting Cloudflare Worker secrets..."

# Set secrets using wrangler
cd ../cloudflare-worker

echo "$DISCORD_PUBLIC_KEY" | npx wrangler secret put DISCORD_PUBLIC_KEY --name "$WORKER_NAME"
echo "$SQS_QUEUE_URL" | npx wrangler secret put SQS_QUEUE_URL --name "$WORKER_NAME"
echo "$AWS_ACCESS_KEY_ID" | npx wrangler secret put AWS_ACCESS_KEY_ID --name "$WORKER_NAME"
echo "$AWS_SECRET_ACCESS_KEY" | npx wrangler secret put AWS_SECRET_ACCESS_KEY --name "$WORKER_NAME"

# Get the worker URL
WORKER_URL="https://$WORKER_NAME.thomas-t-g.workers.dev"

echo ""
echo "✅ Cloudflare Worker deployed successfully!"
echo "🔗 Worker URL: $WORKER_URL"
echo ""
echo "📝 Next steps:"
echo "1. Go to Discord Developer Portal: https://discord.com/developers/applications"
echo "2. Select your bot application"
echo "3. Go to 'General Information'"
echo "4. Set 'Interactions Endpoint URL' to: $WORKER_URL"
echo "5. Save changes"