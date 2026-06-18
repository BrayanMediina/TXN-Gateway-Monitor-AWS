resource "aws_sqs_queue" "dlq" {
  name                       = var.dlq_name
  message_retention_seconds  = 1209600 # 14 días
  visibility_timeout_seconds = 120     # >= dlq_handler Lambda timeout (60s)
  tags                       = { Name = var.dlq_name }
}

resource "aws_sqs_queue" "main" {
  name                       = var.queue_name
  visibility_timeout_seconds = var.visibility_timeout
  message_retention_seconds  = 345600 # 4 días

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.dlq.arn
    maxReceiveCount     = var.max_receive_count
  })

  tags = { Name = var.queue_name }
}

# Política para que SNS pueda enviar a SQS
resource "aws_sqs_queue_policy" "main" {
  queue_url = aws_sqs_queue.main.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "sns.amazonaws.com" }
      Action    = "sqs:SendMessage"
      Resource  = aws_sqs_queue.main.arn
    }]
  })
}

output "queue_arn" { value = aws_sqs_queue.main.arn }
output "dlq_arn"   { value = aws_sqs_queue.dlq.arn }
output "queue_url" { value = aws_sqs_queue.main.url }
