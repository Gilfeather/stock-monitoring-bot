variable "environment" {
  description = "Environment name"
  type        = string
}

variable "project_name" {
  description = "Project name"
  type        = string
}

variable "cloudflare_account_id" {
  description = "Cloudflare account ID"
  type        = string
}

variable "cloudflare_zone_id" {
  description = "Cloudflare zone ID"
  type        = string
  default     = ""
}

variable "aws_region" {
  description = "AWS region"
  type        = string
}

variable "discord_public_key" {
  description = "Discord public key"
  type        = string
  sensitive   = true
}

variable "aws_access_key_id" {
  description = "AWS access key ID for SQS"
  type        = string
  sensitive   = true
}

variable "aws_secret_access_key" {
  description = "AWS secret access key for SQS"
  type        = string
  sensitive   = true
}

variable "sqs_queue_url" {
  description = "SQS queue URL"
  type        = string
}

variable "worker_subdomain" {
  description = "Worker subdomain"
  type        = string
  default     = "discord-webhook"
}

variable "worker_domain" {
  description = "Worker domain (if using custom domain)"
  type        = string
  default     = ""
}