variable "aws_region" {
  description = "Región de AWS donde se desplegará la infraestructura"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Entorno de despliegue (dev, staging, production)"
  type        = string
  default     = "dev"
  validation {
    condition     = contains(["dev", "staging", "production"], var.environment)
    error_message = "El entorno debe ser dev, staging o production."
  }
}

variable "alert_email" {
  description = "Email para recibir alertas SNS"
  type        = string
}

variable "ecr_image_uri" {
  description = "URI de la imagen Docker en ECR (account.dkr.ecr.region.amazonaws.com/repo:tag)"
  type        = string
  default     = ""
}

variable "github_repo" {
  description = "Repo GitHub en formato owner/repo para el OIDC trust policy"
  type        = string
  default     = "BrayanMediina/TXN-Gateway-Monitor-AWS"
}

