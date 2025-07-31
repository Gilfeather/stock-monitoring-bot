output "api_gateway_url" {
  description = "API Gateway URL"
  value       = "${aws_api_gateway_rest_api.discord_interactions.execution_arn}/${var.environment}"
}

output "execution_arn" {
  description = "API Gateway execution ARN"
  value       = aws_api_gateway_rest_api.discord_interactions.execution_arn
}

output "invoke_url" {
  description = "API Gateway invoke URL"
  value       = "https://${aws_api_gateway_rest_api.discord_interactions.id}.execute-api.${data.aws_region.current.name}.amazonaws.com/${var.environment}/interactions"
}