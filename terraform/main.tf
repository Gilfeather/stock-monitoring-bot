terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    bucket  = "kamiforge-terraform-state"
    key     = "stock-monitoring-bot/terraform.tfstate"
    region  = "ap-northeast-1"
    profile = "polarmap"
  }
}

provider "aws" {
  region  = var.aws_region
  profile = var.aws_profile
}

# DynamoDBテーブル
module "dynamodb" {
  source = "./modules/dynamodb"

  environment  = var.environment
  project_name = var.project_name
}

# Parameter Store for secrets
resource "aws_ssm_parameter" "discord_webhook_url" {
  name  = "/${var.project_name}/${var.environment}/discord-webhook-url"
  type  = "SecureString"
  value = var.discord_webhook_url

  tags = {
    Environment = var.environment
    Project     = var.project_name
  }
}

resource "aws_ssm_parameter" "alpha_vantage_api_key" {
  name  = "/${var.project_name}/${var.environment}/alpha-vantage-api-key"
  type  = "SecureString"
  value = var.alpha_vantage_api_key

  tags = {
    Environment = var.environment
    Project     = var.project_name
  }
}

resource "aws_ssm_parameter" "discord_public_key" {
  name  = "/${var.project_name}/${var.environment}/discord-public-key"
  type  = "SecureString"
  value = var.discord_public_key

  tags = {
    Environment = var.environment
    Project     = var.project_name
  }
}

resource "aws_ssm_parameter" "user_ids" {
  name  = "/${var.project_name}/${var.environment}/user-ids"
  type  = "String"
  value = var.user_ids

  tags = {
    Environment = var.environment
    Project     = var.project_name
  }
}

# Lambda関数
module "lambda" {
  source = "./modules/lambda"

  environment                          = var.environment
  project_name                         = var.project_name
  dynamodb_table_arns                  = module.dynamodb.table_arns
  discord_webhook_parameter_name       = aws_ssm_parameter.discord_webhook_url.name
  alpha_vantage_api_key_parameter_name = aws_ssm_parameter.alpha_vantage_api_key.name
  discord_public_key_parameter_name    = aws_ssm_parameter.discord_public_key.name
  target_users_parameter_name          = aws_ssm_parameter.user_ids.name
  api_gateway_execution_arn            = module.api_gateway.execution_arn
}

# API Gateway for Discord Interactions
module "api_gateway" {
  source = "./modules/api_gateway"

  environment         = var.environment
  project_name        = var.project_name
  lambda_function_arn = module.lambda.function_arn
}
