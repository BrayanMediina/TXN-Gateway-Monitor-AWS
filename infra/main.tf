terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
  # Para portfolio: backend local. En producción usar S3+DynamoDB
  backend "local" {}
}

provider "aws" {
  region = var.aws_region
  default_tags {
    tags = {
      Project     = "txn-gateway-monitor"
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

module "sqs" {
  source             = "./modules/sqs"
  queue_name         = "txn-events-queue"
  dlq_name           = "txn-dlq"
  visibility_timeout = 30
  max_receive_count  = 3
}

module "sns" {
  source             = "./modules/sns"
  gateway_topic_name = "txn-gateway-topic"
  alerts_topic_name  = "txn-alerts-topic"
  alert_email        = var.alert_email
  sqs_queue_arn      = module.sqs.queue_arn
}

module "dynamodb" {
  source             = "./modules/dynamodb"
  txn_table_name     = "txn-events"
  metrics_table_name = "gw-metrics"
}

module "lambda" {
  source                  = "./modules/lambda"
  processor_function_name = "txn-processor"
  dlq_function_name       = "dlq-reprocessor"
  reconcile_function_name = "txn-reconcile"
  sqs_queue_arn           = module.sqs.queue_arn
  dlq_arn                 = module.sqs.dlq_arn
  dynamodb_table_arn      = module.dynamodb.txn_table_arn
  dynamodb_table_name     = module.dynamodb.txn_table_name
  sns_alerts_arn          = module.sns.alerts_topic_arn
  main_queue_url          = module.sqs.queue_url
}

module "eventbridge" {
  source                = "./modules/eventbridge"
  reconcile_lambda_arn  = module.lambda.reconcile_arn
  reconcile_lambda_name = module.lambda.reconcile_name
}

module "ecs" {
  source             = "./modules/ecs"
  service_name       = "gateway-service"
  ecr_image_uri      = var.ecr_image_uri
  dynamodb_table_arn = module.dynamodb.txn_table_arn
  sns_topic_arn      = module.sns.gateway_topic_arn
  sns_alerts_arn     = module.sns.alerts_topic_arn
  aws_region         = var.aws_region
}

# ── Frontend: S3 + CloudFront ─────────────────────────────────────────────────
module "frontend" {
  source = "./modules/frontend"
}

# ── API Gateway: HTTPS proxy → ECS ───────────────────────────────────────────
module "apigw" {
  source    = "./modules/apigw"
  cf_domain = module.frontend.domain_name
  ecs_ip    = var.ecs_initial_ip
}

output "api_gateway_url" {
  value       = module.apigw.api_endpoint
  description = "URL HTTPS del API Gateway — configura como VITE_API_URL en .env.production"
}

output "api_gateway_id" {
  value       = module.apigw.api_id
  description = "ID del API Gateway — configura como secret API_GW_ID"
}

output "api_gateway_integration_id" {
  value       = module.apigw.integration_id
  description = "ID de la integración ECS — configura como secret API_GW_INTEGRATION_ID"
}

output "frontend_url" {
  value       = "https://${module.frontend.domain_name}"
  description = "URL pública del dashboard React vía CloudFront"
}

output "frontend_s3_bucket" {
  value       = module.frontend.bucket_name
  description = "Bucket S3 del frontend — configura como secret FRONTEND_S3_BUCKET"
}

output "cloudfront_distribution_id" {
  value       = module.frontend.distribution_id
  description = "ID de la distribución CloudFront — configura como secret CLOUDFRONT_DISTRIBUTION_ID"
}

# ── Phase 5: GitHub Actions OIDC ─────────────────────────────────────────────
data "aws_caller_identity" "current" {}

resource "aws_iam_openid_connect_provider" "github" {
  url             = "https://token.actions.githubusercontent.com"
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = ["6938fd4d98bab03faadb97b34396831e3780aea1"]
}

resource "aws_iam_role" "github_actions_deploy" {
  name = "txn-gateway-github-actions-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Action    = "sts:AssumeRoleWithWebIdentity"
      Principal = { Federated = aws_iam_openid_connect_provider.github.arn }
      Condition = {
        StringEquals = {
          "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
        }
        StringLike = {
          "token.actions.githubusercontent.com:sub" = "repo:${var.github_repo}:*"
        }
      }
    }]
  })
}

resource "aws_iam_role_policy" "github_actions_deploy" {
  name = "txn-gateway-github-actions-policy"
  role = aws_iam_role.github_actions_deploy.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ecr:GetAuthorizationToken",
          "ecr:BatchCheckLayerAvailability",
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage",
          "ecr:PutImage",
          "ecr:InitiateLayerUpload",
          "ecr:UploadLayerPart",
          "ecr:CompleteLayerUpload"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "ecs:UpdateService",
          "ecs:DescribeServices",
          "ecs:ListTasks",
          "ecs:DescribeTasks"
        ]
        Resource = "*"
      },
      {
        Effect   = "Allow"
        Action   = ["ec2:DescribeNetworkInterfaces"]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = ["lambda:UpdateFunctionCode"]
        Resource = [
          "arn:aws:lambda:${var.aws_region}:${data.aws_caller_identity.current.account_id}:function:txn-*",
          "arn:aws:lambda:${var.aws_region}:${data.aws_caller_identity.current.account_id}:function:dlq-*"
        ]
      },
      {
        Effect = "Allow"
        Action = ["s3:PutObject", "s3:DeleteObject", "s3:ListBucket"]
        Resource = [
          module.frontend.bucket_arn,
          "${module.frontend.bucket_arn}/*"
        ]
      },
      {
        Effect   = "Allow"
        Action   = ["cloudfront:CreateInvalidation"]
        Resource = "arn:aws:cloudfront::${data.aws_caller_identity.current.account_id}:distribution/${module.frontend.distribution_id}"
      },
      {
        Effect   = "Allow"
        Action   = ["apigateway:PATCH"]
        Resource = "arn:aws:apigateway:${var.aws_region}::/apis/${module.apigw.api_id}/integrations/*"
      }
    ]
  })
}

output "github_actions_role_arn" {
  value       = aws_iam_role.github_actions_deploy.arn
  description = "ARN del rol OIDC para GitHub Actions — configura como secret AWS_DEPLOY_ROLE_ARN"
}

# ── Phase 5: CloudWatch Dashboard ────────────────────────────────────────────
locals {
  dlq_alarm_arn = "arn:aws:cloudwatch:${var.aws_region}:${data.aws_caller_identity.current.account_id}:alarm:txn-dlq-messages-visible"

  dashboard_widgets = [
    {
      type   = "text"
      x      = 0
      y      = 0
      width  = 24
      height = 1
      properties = {
        markdown = "## TXN Gateway Monitor — Dashboard Operacional"
      }
    },
    {
      type   = "metric"
      x      = 0
      y      = 1
      width  = 8
      height = 6
      properties = {
        title  = "SQS — Mensajes enviados/recibidos"
        view   = "timeSeries"
        region = var.aws_region
        metrics = [
          ["AWS/SQS", "NumberOfMessagesSent", "QueueName", "txn-events-queue"],
          ["AWS/SQS", "NumberOfMessagesReceived", "QueueName", "txn-events-queue"]
        ]
        period = 60
        stat   = "Sum"
      }
    },
    {
      type   = "metric"
      x      = 8
      y      = 1
      width  = 8
      height = 6
      properties = {
        title  = "DLQ — Mensajes fallidos acumulados"
        view   = "timeSeries"
        region = var.aws_region
        metrics = [
          ["AWS/SQS", "ApproximateNumberOfMessagesVisible", "QueueName", "txn-dlq"]
        ]
        period = 300
        stat   = "Maximum"
      }
    },
    {
      type   = "metric"
      x      = 16
      y      = 1
      width  = 8
      height = 6
      properties = {
        title  = "Lambda — Errores"
        view   = "timeSeries"
        region = var.aws_region
        metrics = [
          ["AWS/Lambda", "Errors", "FunctionName", "txn-processor"],
          ["AWS/Lambda", "Errors", "FunctionName", "dlq-reprocessor"],
          ["AWS/Lambda", "Errors", "FunctionName", "txn-reconcile"]
        ]
        period = 60
        stat   = "Sum"
      }
    },
    {
      type   = "metric"
      x      = 0
      y      = 7
      width  = 8
      height = 6
      properties = {
        title  = "Lambda — Duración P95 (ms)"
        view   = "timeSeries"
        region = var.aws_region
        metrics = [
          ["AWS/Lambda", "Duration", "FunctionName", "txn-processor"],
          ["AWS/Lambda", "Duration", "FunctionName", "dlq-reprocessor"]
        ]
        period = 60
        stat   = "p95"
      }
    },
    {
      type   = "metric"
      x      = 8
      y      = 7
      width  = 8
      height = 6
      properties = {
        title  = "ECS — CPU y Memoria"
        view   = "timeSeries"
        region = var.aws_region
        metrics = [
          ["AWS/ECS", "CPUUtilization", "ClusterName", "txn-gateway-cluster", "ServiceName", "gateway-service"],
          ["AWS/ECS", "MemoryUtilization", "ClusterName", "txn-gateway-cluster", "ServiceName", "gateway-service"]
        ]
        period = 60
        stat   = "Average"
      }
    },
    {
      type   = "metric"
      x      = 16
      y      = 7
      width  = 8
      height = 6
      properties = {
        title  = "SLO — Stuck Transactions"
        view   = "timeSeries"
        region = var.aws_region
        metrics = [
          ["TXNGateway/SLO", "StuckTransactions", "Environment", "dev"]
        ]
        period = 300
        stat   = "Maximum"
      }
    },
    {
      type   = "alarm"
      x      = 0
      y      = 13
      width  = 24
      height = 3
      properties = {
        title  = "Alarmas activas"
        alarms = [local.dlq_alarm_arn]
      }
    }
  ]
}

resource "aws_cloudwatch_dashboard" "txn_gateway" {
  dashboard_name = "TXN-Gateway-Monitor"
  dashboard_body = jsonencode({ widgets = local.dashboard_widgets })
}

output "cloudwatch_dashboard_url" {
  value       = "https://${var.aws_region}.console.aws.amazon.com/cloudwatch/home?region=${var.aws_region}#dashboards:name=TXN-Gateway-Monitor"
  description = "URL del CloudWatch Dashboard"
}

# ── CloudWatch Alarm para DLQ ─────────────────────────────────────────────────
resource "aws_cloudwatch_metric_alarm" "dlq_alarm" {
  alarm_name          = "txn-dlq-messages-visible"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "ApproximateNumberOfMessagesVisible"
  namespace           = "AWS/SQS"
  period              = 300
  statistic           = "Sum"
  threshold           = 5
  alarm_description   = "La DLQ tiene más de 5 mensajes visibles — requiere atención"
  alarm_actions       = [module.sns.alerts_topic_arn]
  dimensions = {
    QueueName = "txn-dlq"
  }
}
