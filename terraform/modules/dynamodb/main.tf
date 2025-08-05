# 株式情報テーブル
resource "aws_dynamodb_table" "stocks" {
  name           = "${var.project_name}-stocks-${var.environment}"
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "symbol"

  attribute {
    name = "symbol"
    type = "S"
  }

  tags = {
    Name        = "${var.project_name}-stocks-${var.environment}"
    Environment = var.environment
  }
}

# アラート履歴テーブル
resource "aws_dynamodb_table" "alerts" {
  name           = "${var.project_name}-alerts-${var.environment}"
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "alert_id"
  range_key      = "timestamp"

  attribute {
    name = "alert_id"
    type = "S"
  }

  attribute {
    name = "timestamp"
    type = "S"
  }

  attribute {
    name = "symbol"
    type = "S"
  }

  global_secondary_index {
    name            = "symbol-timestamp-index"
    hash_key        = "symbol"
    range_key       = "timestamp"
    projection_type = "ALL"
  }

  tags = {
    Name        = "${var.project_name}-alerts-${var.environment}"
    Environment = var.environment
  }
}

# 株価履歴テーブル
resource "aws_dynamodb_table" "history" {
  name           = "${var.project_name}-history-${var.environment}"
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "symbol"
  range_key      = "timestamp"

  attribute {
    name = "symbol"
    type = "S"
  }

  attribute {
    name = "timestamp"
    type = "S"
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  tags = {
    Name        = "${var.project_name}-history-${var.environment}"
    Environment = var.environment
  }
}

# ポートフォリオテーブル
resource "aws_dynamodb_table" "portfolios" {
  name           = "${var.project_name}-portfolios-${var.environment}"
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "portfolio_id"

  attribute {
    name = "portfolio_id"
    type = "S"
  }

  attribute {
    name = "user_id"
    type = "S"
  }

  global_secondary_index {
    name            = "user_id-index"
    hash_key        = "user_id"
    projection_type = "ALL"
  }

  tags = {
    Name        = "${var.project_name}-portfolios-${var.environment}"
    Environment = var.environment
  }
}

# ポートフォリオ保有銘柄テーブル
resource "aws_dynamodb_table" "holdings" {
  name           = "${var.project_name}-holdings-${var.environment}"
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "holding_id"

  attribute {
    name = "holding_id"
    type = "S"
  }

  attribute {
    name = "portfolio_id"
    type = "S"
  }

  global_secondary_index {
    name            = "portfolio_id-index"
    hash_key        = "portfolio_id"
    projection_type = "ALL"
  }

  tags = {
    Name        = "${var.project_name}-holdings-${var.environment}"
    Environment = var.environment
  }
}