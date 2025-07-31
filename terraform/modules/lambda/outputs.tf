output "function_arn" {
  description = "Lambda function ARN"
  value       = aws_lambda_function.stock_monitoring.arn
}

output "function_name" {
  description = "Lambda function name"
  value       = aws_lambda_function.stock_monitoring.function_name
}

output "basic_layer_arn" {
  description = "Lambda basic layer ARN"
  value       = aws_lambda_layer_version.dependencies_basic.arn
}

output "data_layer_arn" {
  description = "Lambda data layer ARN"
  value       = aws_lambda_layer_version.dependencies_data.arn
}
