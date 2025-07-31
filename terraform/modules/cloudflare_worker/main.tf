terraform {
  required_providers {
    cloudflare = {
      source  = "cloudflare/cloudflare"
      version = "~> 4.39"
    }
    null = {
      source  = "hashicorp/null"
      version = "~> 3.0"
    }
  }
}

# Cloudflare Worker Script
resource "cloudflare_workers_script" "discord_webhook_handler" {
  account_id = var.cloudflare_account_id
  name       = "${var.project_name}-discord-webhook-${var.environment}"
  content    = file("${path.module}/../../../cloudflare-worker/dist/worker.js")
  
  # Environment variables
  plain_text_binding {
    name = "AWS_REGION"
    text = var.aws_region
  }
  
  # Secrets (these need to be set via API or dashboard)
  secret_text_binding {
    name = "DISCORD_PUBLIC_KEY"
    text = var.discord_public_key
  }
  
  secret_text_binding {
    name = "AWS_ACCESS_KEY_ID"
    text = var.aws_access_key_id
  }
  
  secret_text_binding {
    name = "AWS_SECRET_ACCESS_KEY"
    text = var.aws_secret_access_key
  }
  
  secret_text_binding {
    name = "SQS_QUEUE_URL"
    text = var.sqs_queue_url
  }
  
  depends_on = [null_resource.build_worker]
}

# Build Cloudflare Worker before deployment
resource "null_resource" "build_worker" {
  triggers = {
    # Rebuild when source files change
    source_hash = filemd5("${path.module}/../../../cloudflare-worker/src/index.ts")
    package_hash = filemd5("${path.module}/../../../cloudflare-worker/package.json")
    wrangler_config = filemd5("${path.module}/../../../cloudflare-worker/wrangler.toml")
  }
  
  provisioner "local-exec" {
    command = "./scripts/build_cloudflare_worker.sh"
    working_dir = "${path.module}/../../../"
  }
}

# Cloudflare Worker Route (if custom domain is provided)
resource "cloudflare_workers_route" "discord_webhook_route" {
  count = var.cloudflare_zone_id != "" ? 1 : 0
  
  zone_id = var.cloudflare_zone_id
  pattern = "${var.worker_subdomain}.${var.worker_domain}/discord-webhook"
  script_name = cloudflare_workers_script.discord_webhook_handler.name
}