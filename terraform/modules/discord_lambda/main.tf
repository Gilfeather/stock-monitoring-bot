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
    aws_lambda_layer_version.dependencies_basic.arn,
    aws_lambda_layer_version.dependencies_data.arn
  ]

  environment {
    variables = {
      ENVIRONMENT = var.environment
      PROJECT_NAME = var.project_name
      DYNAMODB_TABLE_STOCKS = "${var.project_name}-stocks-${var.environment}"
      DYNAMODB_TABLE_ALERTS = "${var.project_name}-alerts-${var.environment}"
      DYNAMODB_TABLE_HISTORY = "${var.project_name}-history-${var.environment}"
      DYNAMODB_TABLE_PORTFOLIOS = "${var.project_name}-portfolios-${var.environment}"
      DYNAMODB_TABLE_HOLDINGS = "${var.project_name}-holdings-${var.environment}"
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

# Lambda Layer（基本依存関係用）
resource "aws_lambda_layer_version" "dependencies_basic" {
  filename         = "../deployment/lambda-layer-basic.zip"
  layer_name       = "${var.project_name}-dependencies-basic-${var.environment}"
  compatible_runtimes = ["python3.13"]
  
  description = "Basic dependencies for stock monitoring bot"
  source_code_hash = filebase64sha256("../deployment/lambda-layer-basic.zip")
}

# Lambda Layer（データ処理用）
resource "aws_lambda_layer_version" "dependencies_data" {
  filename         = "../deployment/lambda-layer-data.zip"
  layer_name       = "${var.project_name}-dependencies-data-${var.environment}"
  compatible_runtimes = ["python3.13"]
  
  description = "Data processing dependencies (pandas, numpy, yfinance)"
  source_code_hash = filebase64sha256("../deployment/lambda-layer-data.zip")
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

# EventBridge (CloudWatch Events) ルール - 株価監視（市場営業時間中）
resource "aws_cloudwatch_event_rule" "stock_monitoring_schedule" {
  name                = "${var.project_name}-monitoring-schedule-${var.environment}"
  description         = "Trigger stock monitoring Lambda function during JST market hours"
  # 平日9:00-15:00 JST（UTC 0:00-6:00）に1時間ごと実行
  schedule_expression = "cron(0 0-6 ? * MON-FRI *)"

  tags = {
    Name        = "${var.project_name}-monitoring-schedule-${var.environment}"
    Environment = var.environment
  }
}

# EventBridge ルール - 含み損益通知（1時間ごと）
resource "aws_cloudwatch_event_rule" "pnl_report_schedule" {
  name                = "${var.project_name}-pnl-schedule-${var.environment}"
  description         = "Trigger PnL report Lambda function every hour"
  # 毎時間実行
  schedule_expression = "cron(0 * * * ? *)"

  tags = {
    Name        = "${var.project_name}-pnl-schedule-${var.environment}"
    Environment = var.environment
  }
}

# EventBridge ターゲット - 株価監視
resource "aws_cloudwatch_event_target" "monitoring_lambda_target" {
  rule      = aws_cloudwatch_event_rule.stock_monitoring_schedule.name
  target_id = "StockMonitoringLambdaTarget"
  arn       = aws_lambda_function.discord_processor.arn
  
  input = jsonencode({
    "source": "aws.events",
    "detail-type": "Scheduled Event",
    "detail": {
      "event_type": "stock_monitoring"
    }
  })

  depends_on = [aws_cloudwatch_event_rule.stock_monitoring_schedule]
}

# EventBridge ターゲット - 含み損益通知
resource "aws_cloudwatch_event_target" "pnl_lambda_target" {
  rule      = aws_cloudwatch_event_rule.pnl_report_schedule.name
  target_id = "PnLReportLambdaTarget"
  arn       = aws_lambda_function.discord_processor.arn
  
  input = jsonencode({
    "source": "aws.events",
    "detail-type": "Scheduled Event",
    "detail": {
      "event_type": "pnl_report"
    }
  })

  depends_on = [aws_cloudwatch_event_rule.pnl_report_schedule]
}

# Lambda関数にEventBridgeからの実行権限を付与 - 株価監視
resource "aws_lambda_permission" "allow_eventbridge_monitoring" {
  statement_id  = "AllowExecutionFromEventBridgeMonitoring"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.discord_processor.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.stock_monitoring_schedule.arn
}

# Lambda関数にEventBridgeからの実行権限を付与 - 含み損益通知
resource "aws_lambda_permission" "allow_eventbridge_pnl" {
  statement_id  = "AllowExecutionFromEventBridgePnL"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.discord_processor.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.pnl_report_schedule.arn
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