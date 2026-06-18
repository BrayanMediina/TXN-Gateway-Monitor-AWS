variable "queue_name" {
  description = "Nombre de la cola SQS principal"
  type        = string
}

variable "dlq_name" {
  description = "Nombre de la Dead Letter Queue"
  type        = string
}

variable "visibility_timeout" {
  description = "Tiempo de visibilidad de mensajes en segundos"
  type        = number
  default     = 30
}

variable "max_receive_count" {
  description = "Número máximo de reintentos antes de enviar a DLQ"
  type        = number
  default     = 3
}
