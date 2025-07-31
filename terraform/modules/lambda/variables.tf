variable "environment" {
  description = "Environment name"
  type        = string
}

variable "project_name" {
  description = "Project name"
  type        = string
}

variable "dynamodb_table_arns" {
  description = "ARNs of DynamoDB tables"
  type        = map(string)
}

variable "discord_webhook_parameter_name" {
  description = "Parameter Store name for Discord webhook URL"
  type        = string
}

variable "alpha_vantage_api_key_parameter_name" {
  description = "Parameter Store name for Alpha Vantage API key"
  type        = string
}

variable "discord_public_key_parameter_name" {
  description = "Parameter Store name for Discord public key"
  type        = string
}

variable "target_users_parameter_name" {
  description = "Parameter Store name for target users (comma-separated)"
  type        = string
}

variable "api_gateway_execution_arn" {
  description = "API Gateway execution ARN"
  type        = string
}