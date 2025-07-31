variable "environment" {
  description = "Environment name"
  type        = string
}

variable "project_name" {
  description = "Project name"
  type        = string
}

variable "sqs_queue_arn" {
  description = "ARN of the SQS queue"
  type        = string
}

variable "sqs_dlq_arn" {
  description = "ARN of the SQS Dead Letter Queue"
  type        = string
}

variable "dynamodb_table_arns" {
  description = "Map of DynamoDB table ARNs"
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

variable "target_users_parameter_name" {
  description = "Parameter Store name for target user IDs"
  type        = string
}

variable "lambda_basic_layer_arn" {
  description = "ARN of the Lambda Basic Layer"
  type        = string
}

variable "lambda_data_layer_arn" {
  description = "ARN of the Lambda Data Layer"
  type        = string
}
