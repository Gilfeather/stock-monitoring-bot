# Dead Letter Queue (FIFO to match main queue)
resource "aws_sqs_queue" "discord_webhook_dlq" {
  name = "${var.project_name}-discord-webhook-dlq-${var.environment}.fifo"
  
  # FIFO queue to match main queue
  fifo_queue                  = true
  content_based_deduplication = true
  
  message_retention_seconds = 1209600 # 14 days
  
  tags = {
    Name        = "${var.project_name}-discord-webhook-dlq-${var.environment}"
    Environment = var.environment
    Project     = var.project_name
  }
}

# Main FIFO Queue for Discord webhook processing
resource "aws_sqs_queue" "discord_webhook" {
  name = "${var.project_name}-discord-webhook-${var.environment}.fifo"
  
  # FIFO queue for deduplication
  fifo_queue                  = true
  content_based_deduplication = true
  deduplication_scope         = "messageGroup"
  fifo_throughput_limit       = "perMessageGroupId"
  
  # Message settings
  message_retention_seconds = 1209600 # 14 days
  visibility_timeout_seconds = 300    # 5 minutes
  receive_wait_time_seconds = 20      # Long polling
  
  # Dead letter queue
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.discord_webhook_dlq.arn
    maxReceiveCount     = 3
  })
  
  tags = {
    Name        = "${var.project_name}-discord-webhook-${var.environment}"
    Environment = var.environment
    Project     = var.project_name
  }
}

# IAM user for Cloudflare Workers to access SQS
resource "aws_iam_user" "cloudflare_sqs_user" {
  name = "${var.project_name}-cloudflare-sqs-${var.environment}"
  
  tags = {
    Name        = "${var.project_name}-cloudflare-sqs-${var.environment}"
    Environment = var.environment
    Project     = var.project_name
  }
}

resource "aws_iam_access_key" "cloudflare_sqs_key" {
  user = aws_iam_user.cloudflare_sqs_user.name
}

resource "aws_iam_user_policy" "cloudflare_sqs_policy" {
  name = "${var.project_name}-cloudflare-sqs-policy-${var.environment}"
  user = aws_iam_user.cloudflare_sqs_user.name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "sqs:SendMessage",
          "sqs:GetQueueUrl",
          "sqs:GetQueueAttributes"
        ]
        Resource = aws_sqs_queue.discord_webhook.arn
      }
    ]
  })
}