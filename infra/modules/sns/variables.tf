variable "gateway_topic_name" {
  description = "Nombre del SNS Topic principal del gateway"
  type        = string
}

variable "alerts_topic_name" {
  description = "Nombre del SNS Topic de alertas"
  type        = string
}

variable "alert_email" {
  description = "Email para suscripción de alertas"
  type        = string
}

variable "sqs_queue_arn" {
  description = "ARN de la cola SQS para fan-out"
  type        = string
}
