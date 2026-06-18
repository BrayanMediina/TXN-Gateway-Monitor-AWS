resource "aws_dynamodb_table" "txn_events" {
  name         = var.txn_table_name
  billing_mode = "PAY_PER_REQUEST" # Free Tier: gratis hasta 25 WCU/RCU en on-demand
  hash_key     = "txnId"
  range_key    = "timestamp"

  attribute {
    name = "txnId"
    type = "S"
  }
  attribute {
    name = "timestamp"
    type = "S"
  }
  attribute {
    name = "status"
    type = "S"
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  global_secondary_index {
    name            = "status-index"
    hash_key        = "status"
    range_key       = "timestamp"
    projection_type = "ALL"
  }

  point_in_time_recovery { enabled = true }

  tags = { Name = var.txn_table_name }
}

resource "aws_dynamodb_table" "gw_metrics" {
  name         = var.metrics_table_name
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "date"
  range_key    = "service"

  attribute {
    name = "date"
    type = "S"
  }
  attribute {
    name = "service"
    type = "S"
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  tags = { Name = var.metrics_table_name }
}

output "txn_table_name"     { value = aws_dynamodb_table.txn_events.name }
output "txn_table_arn"      { value = aws_dynamodb_table.txn_events.arn }
output "metrics_table_name" { value = aws_dynamodb_table.gw_metrics.name }
output "metrics_table_arn"  { value = aws_dynamodb_table.gw_metrics.arn }
