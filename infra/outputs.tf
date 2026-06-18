output "sqs_queue_url" {
  description = "URL de la cola SQS principal"
  value       = module.sqs.queue_url
}

output "sqs_queue_arn" {
  description = "ARN de la cola SQS principal"
  value       = module.sqs.queue_arn
}

output "dlq_arn" {
  description = "ARN de la Dead Letter Queue"
  value       = module.sqs.dlq_arn
}

output "sns_gateway_topic_arn" {
  description = "ARN del SNS Topic principal del gateway"
  value       = module.sns.gateway_topic_arn
}

output "sns_alerts_topic_arn" {
  description = "ARN del SNS Topic de alertas"
  value       = module.sns.alerts_topic_arn
}

output "dynamodb_txn_table_name" {
  description = "Nombre de la tabla DynamoDB de transacciones"
  value       = module.dynamodb.txn_table_name
}

output "dynamodb_txn_table_arn" {
  description = "ARN de la tabla DynamoDB de transacciones"
  value       = module.dynamodb.txn_table_arn
}

output "lambda_processor_arn" {
  description = "ARN de la Lambda txn-processor"
  value       = module.lambda.processor_arn
}

output "lambda_reconcile_arn" {
  description = "ARN de la Lambda txn-reconcile"
  value       = module.lambda.reconcile_arn
}
