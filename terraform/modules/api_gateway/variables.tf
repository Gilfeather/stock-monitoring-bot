variable "environment" {
  description = "Environment name"
  type        = string
}

variable "project_name" {
  description = "Project name"
  type        = string
}

variable "lambda_function_arn" {
  description = "Lambda function ARN"
  type        = string
  default     = ""
}