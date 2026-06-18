variable "cf_domain" {
  description = "CloudFront domain for CORS (e.g. d3q5sjqh5x3d32.cloudfront.net)"
  type        = string
}

variable "ecs_ip" {
  description = "Public IP of the ECS Fargate task — updated by deploy workflow on each push"
  type        = string
}

# ── HTTP API (v2) ─────────────────────────────────────────────────────────────
resource "aws_apigatewayv2_api" "gw" {
  name          = "txn-gateway-http-api"
  protocol_type = "HTTP"
  description   = "HTTPS proxy to ECS Fargate gateway-service"

  cors_configuration {
    allow_origins = ["https://${var.cf_domain}", "http://localhost:3000"]
    allow_methods = ["GET", "POST", "OPTIONS"]
    allow_headers = ["Content-Type", "Authorization"]
    max_age       = 300
  }
}

# ── HTTP_PROXY integration → ECS ─────────────────────────────────────────────
resource "aws_apigatewayv2_integration" "ecs" {
  api_id             = aws_apigatewayv2_api.gw.id
  integration_type   = "HTTP_PROXY"
  integration_method = "ANY"
  integration_uri    = "http://${var.ecs_ip}:8000/{proxy}"
}

# ── Routes ────────────────────────────────────────────────────────────────────
resource "aws_apigatewayv2_route" "proxy" {
  api_id    = aws_apigatewayv2_api.gw.id
  route_key = "ANY /{proxy+}"
  target    = "integrations/${aws_apigatewayv2_integration.ecs.id}"
}

# ── Default stage (auto-deploy) ───────────────────────────────────────────────
resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.gw.id
  name        = "$default"
  auto_deploy = true
}

output "api_endpoint"   { value = aws_apigatewayv2_api.gw.api_endpoint }
output "api_id"         { value = aws_apigatewayv2_api.gw.id }
output "integration_id" { value = aws_apigatewayv2_integration.ecs.id }
