output "table_arns" {
  description = "ARNs of DynamoDB tables"
  value = {
    stocks  = aws_dynamodb_table.stocks.arn
    alerts  = aws_dynamodb_table.alerts.arn
    history = aws_dynamodb_table.history.arn
  }
}

output "table_names" {
  description = "Names of DynamoDB tables"
  value = {
    stocks  = aws_dynamodb_table.stocks.name
    alerts  = aws_dynamodb_table.alerts.name
    history = aws_dynamodb_table.history.name
  }
}