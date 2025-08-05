# SQS outputs
output "sqs_queue_url" {
  description = "SQS Queue URL"
  value       = module.sqs.queue_url
}

output "sqs_queue_arn" {
  description = "SQS Queue ARN"
  value       = module.sqs.queue_arn
}

# Cloudflare IAM credentials
output "cloudflare_access_key_id" {
  description = "Access Key ID for Cloudflare Workers"
  value       = module.sqs.cloudflare_access_key_id
}

output "cloudflare_secret_access_key" {
  description = "Secret Access Key for Cloudflare Workers"
  value       = module.sqs.cloudflare_secret_access_key
  sensitive   = true
}

# Cloudflare Worker outputs
output "cloudflare_worker_url" {
  description = "Cloudflare Worker URL"
  value       = module.cloudflare_worker.worker_url
}

output "cloudflare_worker_name" {
  description = "Cloudflare Worker Name"
  value       = module.cloudflare_worker.worker_name
}

# Discord Lambda outputs
output "discord_lambda_function_name" {
  description = "Discord Lambda Function Name"
  value       = module.discord_lambda.function_name
}

