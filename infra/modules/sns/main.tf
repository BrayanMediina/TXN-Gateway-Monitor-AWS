resource "aws_sns_topic" "gateway" {
  name = var.gateway_topic_name
  tags = { Name = var.gateway_topic_name }
}

resource "aws_sns_topic" "alerts" {
  name = var.alerts_topic_name
  tags = { Name = var.alerts_topic_name }
}

# Suscripción email para alertas
resource "aws_sns_topic_subscription" "alert_email" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

# Suscripción SQS: fan-out desde gateway topic → txn-events-queue
resource "aws_sns_topic_subscription" "sqs_fanout" {
  topic_arn = aws_sns_topic.gateway.arn
  protocol  = "sqs"
  endpoint  = var.sqs_queue_arn

  raw_message_delivery = false
}

output "gateway_topic_arn" { value = aws_sns_topic.gateway.arn }
output "alerts_topic_arn"  { value = aws_sns_topic.alerts.arn }
