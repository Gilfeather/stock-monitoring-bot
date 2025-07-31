# IAM role for Discord webhook Lambda
resource "aws_iam_role" "discord_lambda_role" {
  name = "${var.project_name}-discord-lambda-role-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
}

# Basic Lambda execution policy
resource "aws_iam_role_policy_attachment" "discord_lambda_basic" {
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
  role       = aws_iam_role.discord_lambda_role.name
}

# SQS access policy for Lambda
resource "aws_iam_role_policy" "discord_lambda_sqs_policy" {
  name = "${var.project_name}-discord-lambda-sqs-${var.environment}"
  role = aws_iam_role.discord_lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes"
        ]
        Resource = [
          var.sqs_queue_arn,
          var.sqs_dlq_arn
        ]
      }
    ]
  })
}

# DynamoDB access policy for Discord Lambda
resource "aws_iam_role_policy" "discord_lambda_dynamodb_policy" {
  name = "${var.project_name}-discord-lambda-dynamodb-${var.environment}"
  role = aws_iam_role.discord_lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:DeleteItem",
          "dynamodb:Query",
          "dynamodb:Scan"
        ]
        Resource = values(var.dynamodb_table_arns)
      }
    ]
  })
}

# Parameter Store access policy
resource "aws_iam_role_policy" "discord_lambda_parameter_store_policy" {
  name = "${var.project_name}-discord-lambda-parameter-store-${var.environment}"
  role = aws_iam_role.discord_lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ssm:GetParameter",
          "ssm:GetParameters"
        ]
        Resource = [
          "arn:aws:ssm:*:*:parameter/${var.project_name}/${var.environment}/*"
        ]
      }
    ]
  })
}

# Lambda function for Discord webhook processing
resource "aws_lambda_function" "discord_processor" {
  filename         = "../deployment/discord-lambda-function.zip"
  function_name    = "${var.project_name}-discord-processor-${var.environment}"
  role            = aws_iam_role.discord_lambda_role.arn
  handler         = "discord_processor.handler"
  runtime         = "python3.13"
  timeout         = 300
  memory_size     = 1024
  
  source_code_hash = filebase64sha256("../deployment/discord-lambda-function.zip")

  layers = [
    var.lambda_basic_layer_arn,
    var.lambda_data_layer_arn
  ]

  environment {
    variables = {
      ENVIRONMENT = var.environment
      PROJECT_NAME = var.project_name
      DYNAMODB_TABLE_STOCKS = "${var.project_name}-stocks-${var.environment}"
      DYNAMODB_TABLE_ALERTS = "${var.project_name}-alerts-${var.environment}"
      DYNAMODB_TABLE_HISTORY = "${var.project_name}-history-${var.environment}"
      DISCORD_WEBHOOK_PARAMETER = var.discord_webhook_parameter_name
      ALPHA_VANTAGE_API_KEY_PARAMETER = var.alpha_vantage_api_key_parameter_name
      USER_IDS_PARAMETER = var.target_users_parameter_name
    }
  }

  depends_on = [
    aws_iam_role_policy_attachment.discord_lambda_basic,
    aws_iam_role_policy.discord_lambda_sqs_policy,
    aws_iam_role_policy.discord_lambda_dynamodb_policy,
    aws_iam_role_policy.discord_lambda_parameter_store_policy,
  ]

  tags = {
    Name        = "${var.project_name}-discord-processor-${var.environment}"
    Environment = var.environment
    Project     = var.project_name
  }
}

# SQS trigger for Lambda
resource "aws_lambda_event_source_mapping" "discord_sqs_trigger" {
  event_source_arn = var.sqs_queue_arn
  function_name    = aws_lambda_function.discord_processor.arn
  
  batch_size                         = 1
  maximum_batching_window_in_seconds = 0
  
  # Error handling
  function_response_types = ["ReportBatchItemFailures"]
}

# CloudWatch Log Group
resource "aws_cloudwatch_log_group" "discord_processor_logs" {
  name              = "/aws/lambda/${aws_lambda_function.discord_processor.function_name}"
  retention_in_days = 14

  tags = {
    Name        = "${var.project_name}-discord-processor-logs-${var.environment}"
    Environment = var.environment
    Project     = var.project_name
  }
}