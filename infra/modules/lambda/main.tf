data "aws_iam_policy_document" "lambda_assume_role" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

# ── IAM Role compartido para todas las Lambdas ──────────────────────────────
resource "aws_iam_role" "lambda_exec" {
  name               = "txn-gateway-lambda-role"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
}

resource "aws_iam_role_policy" "lambda_policy" {
  name = "txn-gateway-lambda-policy"
  role = aws_iam_role.lambda_exec.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Effect   = "Allow"
        Action   = ["sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes", "sqs:SendMessage"]
        Resource = [var.sqs_queue_arn, var.dlq_arn]
      },
      {
        Effect   = "Allow"
        Action   = ["dynamodb:PutItem", "dynamodb:GetItem", "dynamodb:UpdateItem", "dynamodb:Query", "dynamodb:Scan"]
        Resource = [var.dynamodb_table_arn, "${var.dynamodb_table_arn}/index/*"]
      },
      {
        Effect   = "Allow"
        Action   = ["sns:Publish"]
        Resource = var.sns_alerts_arn
      },
      {
        Effect   = "Allow"
        Action   = ["cloudwatch:PutMetricData"]
        Resource = "*"
      }
    ]
  })
}

# ── Lambda: txn-processor ───────────────────────────────────────────────────
data "archive_file" "processor" {
  type        = "zip"
  source_file = "${path.module}/../../../lambdas/txn_processor/handler.py"
  output_path = "/tmp/txn_processor.zip"
}

resource "aws_lambda_function" "processor" {
  function_name    = var.processor_function_name
  role             = aws_iam_role.lambda_exec.arn
  handler          = "handler.handler"
  runtime          = "python3.12"
  filename         = data.archive_file.processor.output_path
  source_code_hash = data.archive_file.processor.output_base64sha256
  timeout          = 30
  memory_size      = 256

  environment {
    variables = {
      DYNAMODB_TABLE       = var.dynamodb_table_name
      SNS_ALERTS_TOPIC_ARN = var.sns_alerts_arn
      HIGH_VALUE_THRESHOLD = "50000"
      LOG_LEVEL            = "INFO"
    }
  }

  tags = { Name = var.processor_function_name }
}

resource "aws_lambda_event_source_mapping" "sqs_trigger" {
  event_source_arn        = var.sqs_queue_arn
  function_name           = aws_lambda_function.processor.arn
  batch_size              = 10
  function_response_types = ["ReportBatchItemFailures"]
}

# ── Lambda: dlq-reprocessor ─────────────────────────────────────────────────
data "archive_file" "dlq_handler" {
  type        = "zip"
  source_file = "${path.module}/../../../lambdas/dlq_handler/handler.py"
  output_path = "/tmp/dlq_handler.zip"
}

resource "aws_lambda_function" "dlq_handler" {
  function_name    = var.dlq_function_name
  role             = aws_iam_role.lambda_exec.arn
  handler          = "handler.handler"
  runtime          = "python3.12"
  filename         = data.archive_file.dlq_handler.output_path
  source_code_hash = data.archive_file.dlq_handler.output_base64sha256
  timeout          = 60
  memory_size      = 256

  environment {
    variables = {
      DYNAMODB_TABLE = var.dynamodb_table_name
      MAIN_QUEUE_URL = var.main_queue_url
      MAX_RETRIES    = "3"
      LOG_LEVEL      = "INFO"
    }
  }

  tags = { Name = var.dlq_function_name }
}

resource "aws_lambda_event_source_mapping" "dlq_trigger" {
  event_source_arn        = var.dlq_arn
  function_name           = aws_lambda_function.dlq_handler.arn
  batch_size              = 5
  function_response_types = ["ReportBatchItemFailures"]
}

# ── Lambda: txn-reconcile ───────────────────────────────────────────────────
data "archive_file" "reconcile" {
  type        = "zip"
  source_file = "${path.module}/../../../lambdas/reconcile/handler.py"
  output_path = "/tmp/txn_reconcile.zip"
}

resource "aws_lambda_function" "reconcile" {
  function_name    = var.reconcile_function_name
  role             = aws_iam_role.lambda_exec.arn
  handler          = "handler.handler"
  runtime          = "python3.12"
  filename         = data.archive_file.reconcile.output_path
  source_code_hash = data.archive_file.reconcile.output_base64sha256
  timeout          = 60
  memory_size      = 256

  environment {
    variables = {
      DYNAMODB_TABLE            = var.dynamodb_table_name
      SNS_ALERTS_TOPIC_ARN      = var.sns_alerts_arn
      PENDING_THRESHOLD_MINUTES = "10"
      APP_ENV                   = "dev"
      LOG_LEVEL                 = "INFO"
    }
  }

  tags = { Name = var.reconcile_function_name }
}

output "processor_arn"   { value = aws_lambda_function.processor.arn }
output "dlq_handler_arn" { value = aws_lambda_function.dlq_handler.arn }
output "reconcile_arn"   { value = aws_lambda_function.reconcile.arn }
output "reconcile_name"  { value = aws_lambda_function.reconcile.function_name }
