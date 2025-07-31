output "queue_arn" {
  description = "ARN of the Discord webhook SQS queue"
  value       = aws_sqs_queue.discord_webhook.arn
}

output "queue_url" {
  description = "URL of the Discord webhook SQS queue"
  value       = aws_sqs_queue.discord_webhook.url
}

output "dlq_arn" {
  description = "ARN of the Dead Letter Queue"
  value       = aws_sqs_queue.discord_webhook_dlq.arn
}

output "cloudflare_access_key_id" {
  description = "Access Key ID for Cloudflare Workers"
  value       = aws_iam_access_key.cloudflare_sqs_key.id
}

output "cloudflare_secret_access_key" {
  description = "Secret Access Key for Cloudflare Workers"
  value       = aws_iam_access_key.cloudflare_sqs_key.secret
  sensitive   = true
}