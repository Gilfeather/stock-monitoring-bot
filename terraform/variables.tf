variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "ap-northeast-1"
}

variable "aws_profile" {
  description = "AWS profile"
  type        = string
  default     = "polarmap"
}

variable "environment" {
  description = "Environment name"
  type        = string
}

variable "project_name" {
  description = "Project name"
  type        = string
  default     = "stock-monitoring-bot"
}

variable "discord_webhook_url" {
  description = "Discord webhook URL"
  type        = string
  sensitive   = true
}

variable "alpha_vantage_api_key" {
  description = "Alpha Vantage API key"
  type        = string
  sensitive   = true
}

variable "discord_public_key" {
  description = "Discord Bot Public Key for signature verification"
  type        = string
  sensitive   = true
}

variable "user_ids" {
  description = "Comma-separated list of Discord user IDs for P&L notifications"
  type        = string
  default     = ""
}