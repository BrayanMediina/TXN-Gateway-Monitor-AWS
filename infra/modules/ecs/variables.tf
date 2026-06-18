variable "service_name" {
  description = "Nombre del servicio ECS"
  type        = string
}

variable "ecr_image_uri" {
  description = "URI completo de la imagen en ECR"
  type        = string
  default     = ""
}

variable "dynamodb_table_arn" {
  description = "ARN de la tabla DynamoDB de transacciones"
  type        = string
}

variable "sns_topic_arn" {
  description = "ARN del SNS Topic principal del gateway"
  type        = string
}

variable "sns_alerts_arn" {
  description = "ARN del SNS Topic de alertas"
  type        = string
}

variable "aws_region" {
  description = "Región de AWS"
  type        = string
  default     = "us-east-1"
}
