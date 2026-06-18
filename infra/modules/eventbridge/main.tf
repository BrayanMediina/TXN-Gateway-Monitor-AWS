# Regla 1: Cron cada 5 minutos para reconciliación
resource "aws_cloudwatch_event_rule" "reconcile_schedule" {
  name                = "txn-reconcile-schedule"
  description         = "Dispara reconciliación de transacciones cada 5 minutos"
  schedule_expression = "rate(5 minutes)"
  state               = "ENABLED"
}

resource "aws_cloudwatch_event_target" "reconcile_lambda" {
  rule      = aws_cloudwatch_event_rule.reconcile_schedule.name
  target_id = "ReconcileLambda"
  arn       = var.reconcile_lambda_arn
}

resource "aws_lambda_permission" "allow_eventbridge" {
  statement_id  = "AllowEventBridgeInvoke"
  action        = "lambda:InvokeFunction"
  function_name = var.reconcile_lambda_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.reconcile_schedule.arn
}

# Regla 2: Detección de patrones — transacciones de alto valor
resource "aws_cloudwatch_event_rule" "high_value_txn" {
  name        = "txn-high-value-pattern"
  description = "Detecta transacciones mayores a 50,000 para alerta de fraude"
  event_pattern = jsonencode({
    source      = ["txn.gateway"]
    detail-type = ["TransactionEvent"]
    detail = {
      amount = [{ numeric = [">", 50000] }]
    }
  })
}

# Regla 3: Múltiples fallos
resource "aws_cloudwatch_event_rule" "multiple_failures" {
  name        = "txn-multiple-failures"
  description = "Detecta transacciones con múltiples fallos de reintento"
  event_pattern = jsonencode({
    source      = ["txn.gateway"]
    detail-type = ["TransactionFailed"]
    detail = {
      retry_count = [{ numeric = [">=", 2] }]
    }
  })
}
