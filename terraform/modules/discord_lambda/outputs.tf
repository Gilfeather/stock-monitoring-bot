output "function_arn" {
  description = "ARN of the Discord processor Lambda function"
  value       = aws_lambda_function.discord_processor.arn
}

output "function_name" {
  description = "Name of the Discord processor Lambda function"
  value       = aws_lambda_function.discord_processor.function_name
}