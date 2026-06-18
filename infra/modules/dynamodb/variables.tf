variable "txn_table_name" {
  description = "Nombre de la tabla DynamoDB de transacciones"
  type        = string
  default     = "txn-events"
}

variable "metrics_table_name" {
  description = "Nombre de la tabla DynamoDB de métricas"
  type        = string
  default     = "gw-metrics"
}
