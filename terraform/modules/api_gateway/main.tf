# API Gateway REST API
resource "aws_api_gateway_rest_api" "discord_interactions" {
  name        = "${var.project_name}-interactions-${var.environment}"
  description = "Discord Interactions API for stock monitoring bot"

  endpoint_configuration {
    types = ["REGIONAL"]
  }

  tags = {
    Name        = "${var.project_name}-interactions-${var.environment}"
    Environment = var.environment
  }
}

# API Gateway Resource
resource "aws_api_gateway_resource" "interactions" {
  rest_api_id = aws_api_gateway_rest_api.discord_interactions.id
  parent_id   = aws_api_gateway_rest_api.discord_interactions.root_resource_id
  path_part   = "interactions"
}

# API Gateway Method
resource "aws_api_gateway_method" "interactions_post" {
  rest_api_id   = aws_api_gateway_rest_api.discord_interactions.id
  resource_id   = aws_api_gateway_resource.interactions.id
  http_method   = "POST"
  authorization = "NONE"
}


# API Gateway Integration
resource "aws_api_gateway_integration" "lambda_integration" {
  rest_api_id = aws_api_gateway_rest_api.discord_interactions.id
  resource_id = aws_api_gateway_resource.interactions.id
  http_method = aws_api_gateway_method.interactions_post.http_method

  integration_http_method = "POST"
  type                   = "AWS_PROXY"
  uri                    = "arn:aws:apigateway:${data.aws_region.current.name}:lambda:path/2015-03-31/functions/${var.lambda_function_arn}/invocations"
}


# CloudWatch Log Group for API Gateway
resource "aws_cloudwatch_log_group" "api_gateway_logs" {
  name              = "API-Gateway-Execution-Logs_${aws_api_gateway_rest_api.discord_interactions.id}/${var.environment}"
  retention_in_days = 14

  tags = {
    Name        = "${var.project_name}-api-gateway-logs-${var.environment}"
    Environment = var.environment
  }
}


# API Gateway Account settings for CloudWatch logging
resource "aws_api_gateway_account" "main" {
  cloudwatch_role_arn = aws_iam_role.api_gateway_cloudwatch.arn
}

# IAM Role for API Gateway CloudWatch logging
resource "aws_iam_role" "api_gateway_cloudwatch" {
  name = "${var.project_name}-api-gateway-cloudwatch-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "apigateway.amazonaws.com"
        }
      }
    ]
  })
}

# IAM Policy attachment for API Gateway CloudWatch logging
resource "aws_iam_role_policy_attachment" "api_gateway_cloudwatch" {
  role       = aws_iam_role.api_gateway_cloudwatch.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonAPIGatewayPushToCloudWatchLogs"
}

# API Gateway Method Settings for detailed logging
resource "aws_api_gateway_method_settings" "interactions_settings" {
  rest_api_id = aws_api_gateway_rest_api.discord_interactions.id
  stage_name  = var.environment
  method_path = "*/*"

  settings {
    # Enable detailed CloudWatch metrics
    metrics_enabled = true
    
    # Enable execution logging
    logging_level   = "INFO"
    
    # Log full requests/responses for debugging
    data_trace_enabled = true
    
    # Throttling settings
    throttling_rate_limit  = 100
    throttling_burst_limit = 200
  }

  depends_on = [aws_api_gateway_deployment.interactions_deployment]
}

# API Gateway Deployment
resource "aws_api_gateway_deployment" "interactions_deployment" {
  depends_on = [
    aws_api_gateway_method.interactions_post,
    aws_api_gateway_integration.lambda_integration,
  ]

  rest_api_id = aws_api_gateway_rest_api.discord_interactions.id
  stage_name  = var.environment

  # Force re-deployment when configuration changes
  triggers = {
    redeployment = sha1(jsonencode([
      aws_api_gateway_resource.interactions.id,
      aws_api_gateway_method.interactions_post.id,
      aws_api_gateway_integration.lambda_integration.id,
    ]))
  }

  lifecycle {
    create_before_destroy = true
  }
}


# Data source for current AWS region
data "aws_region" "current" {}