variable "processor_function_name" {
  description = "Nombre de la Lambda procesadora de SQS"
  type        = string
}

variable "dlq_function_name" {
  description = "Nombre de la Lambda procesadora de DLQ"
  type        = string
}

variable "reconcile_function_name" {
  description = "Nombre de la Lambda de reconciliación (EventBridge)"
  type        = string
}

variable "sqs_queue_arn" {
  description = "ARN de la cola SQS principal"
  type        = string
}

variable "dlq_arn" {
  description = "ARN de la Dead Letter Queue"
  type        = string
}

variable "dynamodb_table_arn" {
  description = "ARN de la tabla DynamoDB de transacciones"
  type        = string
}

variable "dynamodb_table_name" {
  description = "Nombre de la tabla DynamoDB de transacciones"
  type        = string
}

variable "sns_alerts_arn" {
  description = "ARN del SNS Topic de alertas"
  type        = string
}

variable "main_queue_url" {
  description = "URL de la cola SQS principal para reencolar desde DLQ"
  type        = string
}
