data "aws_caller_identity" "current" {}

# ── ECR Repository ───────────────────────────────────────────────────────────
resource "aws_ecr_repository" "gateway" {
  name                 = "txn-gateway-service"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = { Name = "txn-gateway-service" }
}

# ── ECS Cluster ──────────────────────────────────────────────────────────────
resource "aws_ecs_cluster" "main" {
  name = "txn-gateway-cluster"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  tags = { Name = "txn-gateway-cluster" }
}

# ── IAM Role para ECS Task ───────────────────────────────────────────────────
resource "aws_iam_role" "ecs_task_execution" {
  name = "txn-gateway-ecs-execution-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Action    = "sts:AssumeRole"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_execution_policy" {
  role       = aws_iam_role.ecs_task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role" "ecs_task" {
  name = "txn-gateway-ecs-task-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Action    = "sts:AssumeRole"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy" "ecs_task_policy" {
  name = "txn-gateway-ecs-task-policy"
  role = aws_iam_role.ecs_task.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["dynamodb:PutItem", "dynamodb:GetItem", "dynamodb:UpdateItem", "dynamodb:Query", "dynamodb:Scan"]
        Resource = [var.dynamodb_table_arn, "${var.dynamodb_table_arn}/index/*"]
      },
      {
        Effect   = "Allow"
        Action   = ["sqs:GetQueueUrl", "sqs:GetQueueAttributes"]
        Resource = "*"
      },
      {
        Effect   = "Allow"
        Action   = ["sns:Publish"]
        Resource = [var.sns_topic_arn, var.sns_alerts_arn]
      },
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Effect   = "Allow"
        Action   = ["xray:PutTraceSegments", "xray:PutTelemetryRecords"]
        Resource = "*"
      }
    ]
  })
}

# ── CloudWatch Log Group ──────────────────────────────────────────────────────
resource "aws_cloudwatch_log_group" "gateway" {
  name              = "/ecs/gateway-service"
  retention_in_days = 7
}

# ── ECS Task Definition ───────────────────────────────────────────────────────
resource "aws_ecs_task_definition" "gateway" {
  family                   = var.service_name
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 256
  memory                   = 512
  execution_role_arn       = aws_iam_role.ecs_task_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([{
    name      = var.service_name
    image     = var.ecr_image_uri != "" ? var.ecr_image_uri : "${aws_ecr_repository.gateway.repository_url}:latest"
    essential = true

    portMappings = [{
      containerPort = 8000
      protocol      = "tcp"
    }]

    environment = [
      { name = "APP_ENV", value = "production" },
      { name = "LOG_LEVEL", value = "INFO" },
      { name = "DYNAMODB_TXN_TABLE", value = "txn-events" },
      { name = "DYNAMODB_METRICS_TABLE", value = "gw-metrics" },
      { name = "SNS_GATEWAY_TOPIC_ARN", value = var.sns_topic_arn },
      { name = "SNS_ALERTS_TOPIC_ARN", value = var.sns_alerts_arn }
    ]

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.gateway.name
        awslogs-region        = var.aws_region
        awslogs-stream-prefix = "ecs"
      }
    }

    healthCheck = {
      command     = ["CMD-SHELL", "python -c \"import urllib.request; urllib.request.urlopen('http://localhost:8000/health')\" || exit 1"]
      interval    = 30
      timeout     = 10
      retries     = 3
      startPeriod = 10
    }
  }])

  tags = { Name = var.service_name }
}

# ── Red: default VPC ────────────────────────────────────────────────────────
data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

resource "aws_security_group" "gateway" {
  name        = "txn-gateway-sg"
  description = "Gateway service: permite trafico HTTP en 8000"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    from_port   = 8000
    to_port     = 8000
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "txn-gateway-sg" }
}

# ── ECS Service ──────────────────────────────────────────────────────────────
resource "aws_ecs_service" "gateway" {
  name            = var.service_name
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.gateway.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = data.aws_subnets.default.ids
    security_groups  = [aws_security_group.gateway.id]
    assign_public_ip = true
  }

  lifecycle {
    ignore_changes = [task_definition]
  }

  tags = { Name = var.service_name }
}

output "cluster_name"        { value = aws_ecs_cluster.main.name }
output "task_definition_arn" { value = aws_ecs_task_definition.gateway.arn }
output "ecr_repository_url"  { value = aws_ecr_repository.gateway.repository_url }
output "service_name"        { value = aws_ecs_service.gateway.name }
