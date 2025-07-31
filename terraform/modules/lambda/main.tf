# Lambda実行ロール
resource "aws_iam_role" "lambda_role" {
  name = "${var.project_name}-lambda-role-${var.environment}"

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

# Lambda基本実行ポリシーをアタッチ
resource "aws_iam_role_policy_attachment" "lambda_basic" {
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
  role       = aws_iam_role.lambda_role.name
}

# DynamoDBアクセスポリシー
resource "aws_iam_role_policy" "dynamodb_policy" {
  name = "${var.project_name}-dynamodb-policy-${var.environment}"
  role = aws_iam_role.lambda_role.id

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

# Parameter Storeアクセスポリシー
resource "aws_iam_role_policy" "parameter_store_policy" {
  name = "${var.project_name}-parameter-store-policy-${var.environment}"
  role = aws_iam_role.lambda_role.id

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
      },
      {
        Effect = "Allow"
        Action = [
          "lambda:InvokeFunction"
        ]
        Resource = [
          "arn:aws:lambda:*:*:function:${var.project_name}-${var.environment}"
        ]
      }
    ]
  })
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

# Lambda関数
resource "aws_lambda_function" "stock_monitoring" {
  filename         = "../deployment/lambda-function.zip"
  function_name    = "${var.project_name}-${var.environment}"
  role            = aws_iam_role.lambda_role.arn
  handler         = "stock_monitoring_bot.handlers.main.lambda_handler"
  runtime         = "python3.13"
  timeout         = 30
  memory_size     = 1024
  
  layers = [
    aws_lambda_layer_version.dependencies_basic.arn,
    aws_lambda_layer_version.dependencies_data.arn
  ]
  source_code_hash = filebase64sha256("../deployment/lambda-function.zip")

  environment {
    variables = {
      ENVIRONMENT = var.environment
      DYNAMODB_TABLE_STOCKS = "${var.project_name}-stocks-${var.environment}"
      DYNAMODB_TABLE_ALERTS = "${var.project_name}-alerts-${var.environment}"
      DYNAMODB_TABLE_HISTORY = "${var.project_name}-history-${var.environment}"
      DISCORD_WEBHOOK_PARAMETER = var.discord_webhook_parameter_name
      ALPHA_VANTAGE_API_KEY_PARAMETER = var.alpha_vantage_api_key_parameter_name
      DISCORD_PUBLIC_KEY_PARAMETER = var.discord_public_key_parameter_name
      USER_IDS_PARAMETER = var.target_users_parameter_name
    }
  }

  depends_on = [
    aws_iam_role_policy_attachment.lambda_basic,
    aws_iam_role_policy.dynamodb_policy,
    aws_iam_role_policy.parameter_store_policy,
  ]

  tags = {
    Name        = "${var.project_name}-${var.environment}"
    Environment = var.environment
  }
}

# Lambda関数のバージョン作成（Provisioned Concurrency用）
resource "aws_lambda_alias" "live" {
  name             = "live"
  description      = "Live alias for provisioned concurrency"
  function_name    = aws_lambda_function.stock_monitoring.function_name
  function_version = aws_lambda_function.stock_monitoring.version
}

# Provisioned Concurrency設定（Discord Interactions用）
# resource "aws_lambda_provisioned_concurrency_config" "discord_warm" {
#   function_name                     = aws_lambda_function.stock_monitoring.function_name
#   provisioned_concurrent_executions = 1
#   qualifier                         = aws_lambda_alias.live.name
# }

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
  arn       = aws_lambda_function.stock_monitoring.arn
  
  input = jsonencode({
    "source": "aws.events",
    "detail-type": "Scheduled Event",
    "detail": {
      "event_type": "stock_monitoring"
    }
  })
}

# EventBridge ターゲット - 含み損益通知
resource "aws_cloudwatch_event_target" "pnl_lambda_target" {
  rule      = aws_cloudwatch_event_rule.pnl_report_schedule.name
  target_id = "PnLReportLambdaTarget"
  arn       = aws_lambda_function.stock_monitoring.arn
  
  input = jsonencode({
    "source": "aws.events",
    "detail-type": "Scheduled Event",
    "detail": {
      "event_type": "pnl_report"
    }
  })
}

# Lambda関数にEventBridgeからの実行権限を付与 - 株価監視
resource "aws_lambda_permission" "allow_eventbridge_monitoring" {
  statement_id  = "AllowExecutionFromEventBridgeMonitoring"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.stock_monitoring.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.stock_monitoring_schedule.arn
}

# Lambda関数にEventBridgeからの実行権限を付与 - 含み損益通知
resource "aws_lambda_permission" "allow_eventbridge_pnl" {
  statement_id  = "AllowExecutionFromEventBridgePnL"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.stock_monitoring.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.pnl_report_schedule.arn
}

# Lambda関数にAPI Gatewayからの実行権限を付与
resource "aws_lambda_permission" "allow_api_gateway" {
  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.stock_monitoring.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${var.api_gateway_execution_arn}/*/*"
}