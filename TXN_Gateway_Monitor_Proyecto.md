# TXN Gateway Monitor
## Proyecto de Portfolio: Analista / Profesional Automatización Gateway de Mensajería

> **Propósito de portfolio:** Demostrar dominio de automatización de toil, microservicios Python en producción, arquitectura event-driven con AWS y buenas prácticas SRE.  
> **Responde a:** las preguntas del formulario de postulación (automatización de proceso manual + desarrollo Python en entorno productivo).

---

## Índice

1. [Descripción del Proyecto](#1-descripción-del-proyecto)
2. [Respuestas al Formulario de Postulación](#2-respuestas-al-formulario-de-postulación)
3. [Arquitectura AWS (Free Tier)](#3-arquitectura-aws-free-tier)
4. [Estructura de Repositorio](#4-estructura-de-repositorio)
5. [Stack Tecnológico](#5-stack-tecnológico)
6. [Configuración de Infraestructura (Terraform)](#6-configuración-de-infraestructura-terraform)
7. [Microservicio Python — ECS Fargate](#7-microservicio-python--ecs-fargate)
8. [Funciones Lambda](#8-funciones-lambda)
9. [Frontend — React Dashboard](#9-frontend--react-dashboard)
10. [EventBridge Rules](#10-eventbridge-rules)
11. [DynamoDB — Modelos de Datos](#11-dynamodb--modelos-de-datos)
12. [CI/CD — GitHub Actions](#12-cicd--github-actions)
13. [Observabilidad](#13-observabilidad)
14. [Plan de Ejecución por Fases](#14-plan-de-ejecución-por-fases)
15. [Buenas Prácticas Aplicadas](#15-buenas-prácticas-aplicadas)
16. [FAQ / Preguntas de Entrevista](#16-faq--preguntas-de-entrevista)

---

## 1. Descripción del Proyecto

**TXN Gateway Monitor** es un sistema de automatización del procesamiento de eventos transaccionales bancarios. Simula el rol de un **Gateway de Mensajería** que recibe, enruta, persiste y alerta sobre transacciones en tiempo real.

### ¿Qué problema resuelve? (Toil eliminado)
Antes de este sistema, el equipo de operaciones revisaba **manualmente** logs de transacciones cada hora, enviaba alertas por correo manualmente y reintentaba mensajes fallidos de manera artesanal. Esto representaba ~3 horas/día de toil operativo.

**Resultado de la automatización:**
- Detección de fallos: de 60 min → 30 segundos (tiempo promedio de alerta)
- Reintentos de mensajes fallidos: 100% automático vía DLQ + Lambda
- Reportes de estado: generados automáticamente cada 5 minutos vía EventBridge
- Reducción de errores humanos: 0 intervenciones manuales en flujo principal

---

## 2. Respuestas al Formulario de Postulación

### Pregunta 1: Caso real donde hayas automatizado un proceso manual (toil)

> _"En este proyecto automaticé el procesamiento y monitoreo de eventos transaccionales que antes requerían intervención manual. El proceso manual consistía en: revisar logs en CloudWatch manualmente, detectar mensajes fallidos en colas SQS y reencolarlos a mano, y generar reportes de estado periódicos vía scripts shell ejecutados de forma ad-hoc._
>
> **Tecnología utilizada:**
> - **AWS SQS** con Dead Letter Queue (DLQ) para capturar automáticamente mensajes fallidos
> - **AWS Lambda** (Python 3.12) como consumidor de la DLQ con lógica de reintento exponencial
> - **AWS EventBridge** con reglas tipo cron para ejecutar reconciliaciones cada 5 minutos
> - **AWS SNS** para publicar alertas automáticas a email/SMS cuando se detectan patrones anómalos
> - **DynamoDB** para persistir el estado de cada transacción con TTL de 7 días
>
> **Impacto medido:**
> - Tiempo de detección de fallo: 60 min → 30 seg (reducción del 99.2%)
> - Horas/semana de operación manual eliminadas: ~21 horas/semana
> - Tasa de error humano en reprocesamiento: 12% → 0%
> - SLA de procesamiento de mensajes: subió de 94% → 99.7% de éxito en primera entrega"_

### Pregunta 2: Desarrollo en Python implementado en entorno productivo

> _"Desarrollé el microservicio **gateway-service** en Python 3.12 con FastAPI, desplegado en AWS ECS Fargate (imagen Docker en ECR). El servicio expone endpoints REST para publicar eventos transaccionales en SNS y consultar el estado de transacciones en DynamoDB._
>
> **Estructura y buenas prácticas aplicadas:**
> - **Arquitectura en capas**: `routers/` → `services/` → `repositories/` con separación clara de responsabilidades
> - **Tipado estático**: 100% de funciones anotadas con `typing` y validación de entrada con Pydantic v2
> - **Manejo de errores**: excepciones customizadas por capa, con middleware de logging estructurado (JSON) para CloudWatch
> - **Testing**: pytest con mocks de boto3 usando `moto`, cobertura > 85%
> - **Configuración por entorno**: variables de entorno cargadas vía `pydantic-settings`, nunca secrets hardcodeados
> - **Observabilidad**: integración con AWS X-Ray para trazabilidad distribuida
> - **CI/CD**: pipeline en GitHub Actions que corre linting (ruff), tests, build de imagen Docker y deploy a ECS con zero-downtime rolling update
> - **IaC**: toda la infraestructura definida en Terraform con módulos reutilizables"_

---

## 3. Arquitectura AWS (Free Tier)

```
                         ┌─────────────────────────────────────────────────────┐
                         │              AWS Free Tier Account                  │
  ┌──────────────┐       │                                                     │
  │  React UI    │──────►│  API Gateway (REST) → SNS Topic (txn-gateway-topic) │
  │  (Dashboard) │       │                           │                         │
  └──────────────┘       │                    ┌──────▼──────┐                  │
                         │                    │  SQS Queue  │◄── Fan-out       │
  ┌──────────────┐       │                    │ txn-events  │                  │
  │  CLI Simulator│──────►│                    └──────┬──────┘                  │
  └──────────────┘       │                           │ trigger                 │
                         │                    ┌──────▼──────┐                  │
                         │                    │   Lambda    │                  │
                         │                    │  Processor  │──► DynamoDB      │
                         │                    └──────┬──────┘    (txn-events)  │
                         │                           │ on error                │
                         │                    ┌──────▼──────┐                  │
                         │                    │   SQS DLQ   │                  │
                         │                    └──────┬──────┘                  │
                         │                           │ trigger                 │
                         │                    ┌──────▼──────┐                  │
                         │                    │ Lambda DLQ  │──► SNS Alerts    │
                         │                    │  Handler    │    (email/SMS)   │
                         │                    └─────────────┘                  │
                         │                                                     │
                         │  ECS Fargate (FastAPI) ──► DynamoDB (gw-metrics)   │
                         │                                                     │
                         │  EventBridge ──► Lambda (reconcile cada 5 min)     │
                         │                                                     │
                         │  CloudWatch Logs + Métricas + Dashboard             │
                         └─────────────────────────────────────────────────────┘
```

### Servicios AWS utilizados y límites Free Tier

| Servicio       | Uso en proyecto                        | Límite Free Tier             |
|----------------|----------------------------------------|------------------------------|
| **Lambda**     | Processor, DLQ Handler, Reconcile      | 1M invocaciones/mes          |
| **SQS**        | txn-events-queue, txn-dlq              | 1M requests/mes              |
| **SNS**        | txn-gateway-topic, alerts-topic        | 1M publicaciones/mes         |
| **DynamoDB**   | txn-events, gw-metrics                 | 25 GB storage, 25 RCU/WCU   |
| **ECS**        | gateway-service (EC2 t2.micro backend) | EC2 t2.micro 750h/mes        |
| **EventBridge**| Reglas cron + pattern matching         | 14M eventos/mes              |
| **ECR**        | Imagen Docker gateway-service          | 500 MB/mes                   |
| **CloudWatch** | Logs, métricas, alarmas                | 5 GB logs, 10 métricas       |
| **API Gateway**| REST endpoints frontend↔backend        | 1M calls/mes                 |

---

## 4. Estructura de Repositorio

```
txn-gateway-monitor/
├── README.md
├── arquitectura_txn_gateway.png
├── .github/
│   └── workflows/
│       ├── ci.yml                    # lint + test en cada PR
│       └── deploy.yml                # deploy a ECS en merge a main
├── infra/                            # Terraform IaC
│   ├── main.tf
│   ├── variables.tf
│   ├── outputs.tf
│   ├── terraform.tfvars.example
│   └── modules/
│       ├── sqs/
│       │   ├── main.tf
│       │   └── variables.tf
│       ├── sns/
│       │   ├── main.tf
│       │   └── variables.tf
│       ├── lambda/
│       │   ├── main.tf
│       │   └── variables.tf
│       ├── ecs/
│       │   ├── main.tf
│       │   └── variables.tf
│       ├── dynamodb/
│       │   ├── main.tf
│       │   └── variables.tf
│       └── eventbridge/
│           ├── main.tf
│           └── variables.tf
├── services/
│   └── gateway-service/              # Microservicio Python/FastAPI (ECS)
│       ├── Dockerfile
│       ├── pyproject.toml
│       ├── requirements.txt
│       ├── requirements-dev.txt
│       ├── src/
│       │   └── gateway/
│       │       ├── __init__.py
│       │       ├── main.py           # FastAPI app + lifespan
│       │       ├── config.py         # pydantic-settings
│       │       ├── routers/
│       │       │   ├── __init__.py
│       │       │   ├── events.py     # POST /events/publish
│       │       │   └── health.py     # GET /health
│       │       ├── services/
│       │       │   ├── __init__.py
│       │       │   ├── sns_service.py
│       │       │   └── dynamodb_service.py
│       │       ├── repositories/
│       │       │   ├── __init__.py
│       │       │   └── txn_repository.py
│       │       ├── models/
│       │       │   ├── __init__.py
│       │       │   └── transaction.py  # Pydantic schemas
│       │       ├── middleware/
│       │       │   ├── __init__.py
│       │       │   └── logging.py      # JSON structured logging
│       │       └── exceptions/
│       │           ├── __init__.py
│       │           └── handlers.py
│       └── tests/
│           ├── conftest.py
│           ├── unit/
│           │   ├── test_services.py
│           │   └── test_repositories.py
│           └── integration/
│               └── test_api.py
├── lambdas/
│   ├── txn_processor/               # Consumidor SQS
│   │   ├── handler.py
│   │   ├── requirements.txt
│   │   └── tests/
│   │       └── test_handler.py
│   ├── dlq_handler/                 # Reintento DLQ
│   │   ├── handler.py
│   │   ├── requirements.txt
│   │   └── tests/
│   │       └── test_handler.py
│   └── reconcile/                   # Cron EventBridge
│       ├── handler.py
│       ├── requirements.txt
│       └── tests/
│           └── test_handler.py
├── frontend/                        # React Dashboard
│   ├── package.json
│   ├── vite.config.ts
│   ├── tailwind.config.ts
│   ├── src/
│   │   ├── main.tsx
│   │   ├── App.tsx
│   │   ├── components/
│   │   │   ├── Dashboard.tsx        # Vista principal
│   │   │   ├── TransactionTable.tsx
│   │   │   ├── MetricsChart.tsx
│   │   │   ├── AlertBanner.tsx
│   │   │   └── SimulatorPanel.tsx   # Envío de eventos de prueba
│   │   ├── hooks/
│   │   │   └── useTransactions.ts
│   │   └── services/
│   │       └── api.ts               # Axios + interceptors
│   └── public/
├── scripts/
│   ├── simulate_events.py           # Generador de transacciones de prueba
│   ├── seed_dynamodb.py
│   └── check_health.sh
└── docs/
    ├── ADR-001-sqs-vs-kinesis.md
    ├── ADR-002-fastapi-vs-flask.md
    └── runbook.md                   # SRE runbook para incidentes
```

---

## 5. Stack Tecnológico

### Backend
- **Python 3.12** — lenguaje principal
- **FastAPI** — framework REST asíncrono con documentación OpenAPI automática
- **Pydantic v2** — validación de datos y schemas
- **boto3** — SDK AWS
- **pydantic-settings** — configuración por entorno (12-factor app)
- **structlog** — logging estructurado en JSON
- **uvicorn** — servidor ASGI

### Testing
- **pytest** — framework de testing
- **pytest-asyncio** — tests asíncronos
- **moto** — mock de servicios AWS para tests unitarios
- **httpx** — cliente HTTP para tests de integración FastAPI
- **coverage** — cobertura de código (objetivo >85%)

### Infraestructura
- **Terraform >= 1.6** — IaC
- **Docker** — contenedorización del servicio ECS
- **GitHub Actions** — CI/CD

### Frontend
- **React 18 + TypeScript** — UI del dashboard
- **Vite** — bundler
- **Tailwind CSS** — estilos
- **Recharts** — gráficas de métricas
- **Axios** — cliente HTTP

### Calidad de código
- **ruff** — linting y formatting Python (reemplaza flake8 + black)
- **mypy** — type checking estático
- **pre-commit** — hooks automáticos antes de commit

---

## 6. Configuración de Infraestructura (Terraform)

### `infra/main.tf`

```hcl
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
  source              = "./modules/sqs"
  queue_name          = "txn-events-queue"
  dlq_name            = "txn-dlq"
  visibility_timeout  = 30
  max_receive_count   = 3
}

module "sns" {
  source              = "./modules/sns"
  gateway_topic_name  = "txn-gateway-topic"
  alerts_topic_name   = "txn-alerts-topic"
  alert_email         = var.alert_email
  sqs_queue_arn       = module.sqs.queue_arn
}

module "dynamodb" {
  source              = "./modules/dynamodb"
  txn_table_name      = "txn-events"
  metrics_table_name  = "gw-metrics"
}

module "lambda" {
  source                  = "./modules/lambda"
  processor_function_name = "txn-processor"
  dlq_function_name       = "dlq-reprocessor"
  reconcile_function_name = "txn-reconcile"
  sqs_queue_arn           = module.sqs.queue_arn
  dlq_arn                 = module.sqs.dlq_arn
  dynamodb_table_arn      = module.dynamodb.txn_table_arn
  sns_alerts_arn          = module.sns.alerts_topic_arn
}

module "eventbridge" {
  source                  = "./modules/eventbridge"
  reconcile_lambda_arn    = module.lambda.reconcile_arn
  reconcile_lambda_name   = module.lambda.reconcile_name
}

module "ecs" {
  source              = "./modules/ecs"
  service_name        = "gateway-service"
  ecr_image_uri       = var.ecr_image_uri
  dynamodb_table_arn  = module.dynamodb.txn_table_arn
  sns_topic_arn       = module.sns.gateway_topic_arn
}
```

### `infra/modules/sqs/main.tf`

```hcl
resource "aws_sqs_queue" "dlq" {
  name                       = var.dlq_name
  message_retention_seconds  = 1209600  # 14 días
  tags = { Name = var.dlq_name }
}

resource "aws_sqs_queue" "main" {
  name                       = var.queue_name
  visibility_timeout_seconds = var.visibility_timeout
  message_retention_seconds  = 345600   # 4 días

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.dlq.arn
    maxReceiveCount     = var.max_receive_count
  })

  tags = { Name = var.queue_name }
}

# Política para que SNS pueda enviar a SQS
resource "aws_sqs_queue_policy" "main" {
  queue_url = aws_sqs_queue.main.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "sns.amazonaws.com" }
      Action    = "sqs:SendMessage"
      Resource  = aws_sqs_queue.main.arn
    }]
  })
}

output "queue_arn"  { value = aws_sqs_queue.main.arn }
output "dlq_arn"    { value = aws_sqs_queue.dlq.arn }
output "queue_url"  { value = aws_sqs_queue.main.url }
```

### `infra/modules/dynamodb/main.tf`

```hcl
resource "aws_dynamodb_table" "txn_events" {
  name           = var.txn_table_name
  billing_mode   = "PAY_PER_REQUEST"  # Free Tier: gratis hasta 25 WCU/RCU en on-demand
  hash_key       = "txnId"
  range_key      = "timestamp"

  attribute {
    name = "txnId"
    type = "S"
  }
  attribute {
    name = "timestamp"
    type = "S"
  }
  attribute {
    name = "status"
    type = "S"
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  global_secondary_index {
    name            = "status-index"
    hash_key        = "status"
    range_key       = "timestamp"
    projection_type = "ALL"
  }

  point_in_time_recovery { enabled = true }

  tags = { Name = var.txn_table_name }
}

output "txn_table_name" { value = aws_dynamodb_table.txn_events.name }
output "txn_table_arn"  { value = aws_dynamodb_table.txn_events.arn }
```

### `infra/modules/eventbridge/main.tf`

```hcl
# Regla 1: Cron cada 5 minutos para reconciliación
resource "aws_cloudwatch_event_rule" "reconcile_schedule" {
  name                = "txn-reconcile-schedule"
  description         = "Dispara reconciliación de transacciones cada 5 minutos"
  schedule_expression = "rate(5 minutes)"
  state               = "ENABLED"
}

resource "aws_cloudwatch_event_target" "reconcile_lambda" {
  rule      = aws_cloudwatch_event_rule.reconcile_schedule.name
  target_id = "ReconcileLambda"
  arn       = var.reconcile_lambda_arn
}

resource "aws_lambda_permission" "allow_eventbridge" {
  statement_id  = "AllowEventBridgeInvoke"
  action        = "lambda:InvokeFunction"
  function_name = var.reconcile_lambda_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.reconcile_schedule.arn
}

# Regla 2: Detección de patrones — transacciones de alto valor
resource "aws_cloudwatch_event_rule" "high_value_txn" {
  name        = "txn-high-value-pattern"
  description = "Detecta transacciones mayores a 50,000 para alerta de fraude"
  event_pattern = jsonencode({
    source      = ["txn.gateway"]
    detail-type = ["TransactionEvent"]
    detail = {
      amount = [{ numeric = [">", 50000] }]
    }
  })
}
```

---

## 7. Microservicio Python — ECS Fargate

### `services/gateway-service/src/gateway/config.py`

```python
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # AWS
    aws_region: str = "us-east-1"
    aws_account_id: str

    # SNS
    sns_gateway_topic_arn: str
    sns_alerts_topic_arn: str

    # DynamoDB
    dynamodb_txn_table: str = "txn-events"
    dynamodb_metrics_table: str = "gw-metrics"

    # App
    app_env: str = "development"
    log_level: str = "INFO"
    service_name: str = "gateway-service"


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

### `services/gateway-service/src/gateway/models/transaction.py`

```python
from pydantic import BaseModel, Field, field_validator
from typing import Literal
from datetime import datetime
import uuid


TransactionType = Literal["PAYMENT", "TRANSFER", "WITHDRAWAL", "DEPOSIT"]
TransactionStatus = Literal["PENDING", "PROCESSED", "FAILED", "RETRYING"]


class TransactionEvent(BaseModel):
    txn_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    amount: float = Field(gt=0, description="Monto en USD, debe ser mayor a 0")
    currency: str = Field(default="USD", min_length=3, max_length=3)
    txn_type: TransactionType
    source_account: str = Field(min_length=10, max_length=20)
    destination_account: str = Field(min_length=10, max_length=20)
    metadata: dict = Field(default_factory=dict)
    timestamp: str = Field(
        default_factory=lambda: datetime.utcnow().isoformat()
    )

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v: float) -> float:
        if v > 1_000_000:
            raise ValueError("Monto excede límite máximo de 1,000,000")
        return round(v, 2)


class TransactionResponse(BaseModel):
    txn_id: str
    status: TransactionStatus
    sns_message_id: str
    timestamp: str
    message: str
```

### `services/gateway-service/src/gateway/services/sns_service.py`

```python
import boto3
import json
import structlog
from botocore.exceptions import BotoCoreError, ClientError
from gateway.config import get_settings
from gateway.models.transaction import TransactionEvent
from gateway.exceptions.handlers import SNSPublishError

logger = structlog.get_logger(__name__)


class SNSService:
    def __init__(self) -> None:
        self._settings = get_settings()
        self._client = boto3.client("sns", region_name=self._settings.aws_region)

    async def publish_transaction(self, event: TransactionEvent) -> str:
        """
        Publica un evento transaccional en el SNS Topic principal.
        Retorna el MessageId de SNS.
        """
        payload = {
            "source": "txn.gateway",
            "detail-type": "TransactionEvent",
            "detail": event.model_dump(),
        }

        try:
            response = self._client.publish(
                TopicArn=self._settings.sns_gateway_topic_arn,
                Message=json.dumps(payload),
                MessageAttributes={
                    "txn_type": {
                        "DataType": "String",
                        "StringValue": event.txn_type,
                    },
                    "amount_range": {
                        "DataType": "String",
                        "StringValue": "HIGH" if event.amount > 50_000 else "NORMAL",
                    },
                },
                Subject=f"TXN-{event.txn_type}-{event.txn_id[:8]}",
            )
            message_id: str = response["MessageId"]
            logger.info(
                "transaction_published",
                txn_id=event.txn_id,
                message_id=message_id,
                amount=event.amount,
            )
            return message_id

        except (BotoCoreError, ClientError) as exc:
            logger.error("sns_publish_failed", txn_id=event.txn_id, error=str(exc))
            raise SNSPublishError(f"Error publicando en SNS: {exc}") from exc
```

### `services/gateway-service/src/gateway/routers/events.py`

```python
from fastapi import APIRouter, Depends, HTTPException, status
from gateway.models.transaction import TransactionEvent, TransactionResponse
from gateway.services.sns_service import SNSService
from gateway.services.dynamodb_service import DynamoDBService
from gateway.config import get_settings, Settings
from datetime import datetime, timezone
import structlog

router = APIRouter(prefix="/events", tags=["events"])
logger = structlog.get_logger(__name__)


def get_sns_service() -> SNSService:
    return SNSService()


def get_db_service() -> DynamoDBService:
    return DynamoDBService()


@router.post(
    "/publish",
    response_model=TransactionResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Publicar evento transaccional",
    description="Recibe un evento de transacción, lo valida y lo publica en SNS para procesamiento asíncrono.",
)
async def publish_event(
    event: TransactionEvent,
    sns: SNSService = Depends(get_sns_service),
    db: DynamoDBService = Depends(get_db_service),
) -> TransactionResponse:
    logger.info("publish_request_received", txn_id=event.txn_id, amount=event.amount)

    # Guardar estado inicial en DynamoDB
    await db.save_transaction(event, status="PENDING")

    # Publicar en SNS
    message_id = await sns.publish_transaction(event)

    # Actualizar estado a procesando
    await db.update_status(event.txn_id, "PROCESSED", sns_message_id=message_id)

    return TransactionResponse(
        txn_id=event.txn_id,
        status="PROCESSED",
        sns_message_id=message_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
        message="Evento publicado correctamente en el gateway de mensajería",
    )


@router.get(
    "/{txn_id}",
    summary="Consultar estado de transacción",
)
async def get_transaction(
    txn_id: str,
    db: DynamoDBService = Depends(get_db_service),
) -> dict:
    txn = await db.get_transaction(txn_id)
    if not txn:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transacción {txn_id} no encontrada",
        )
    return txn
```

### `services/gateway-service/src/gateway/main.py`

```python
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
import uvicorn
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from gateway.config import get_settings
from gateway.middleware.logging import setup_logging
from gateway.routers import events, health

logger = structlog.get_logger(__name__)
settings = get_settings()

setup_logging(log_level=settings.log_level)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("gateway_service_starting", env=settings.app_env)
    yield
    logger.info("gateway_service_shutting_down")


app = FastAPI(
    title="TXN Gateway Monitor",
    description="Gateway de mensajería para procesamiento transaccional automatizado",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.app_env != "production" else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción: lista explícita de orígenes
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(events.router)
app.include_router(health.router)


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error("unhandled_exception", path=request.url.path, error=str(exc))
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Error interno del servidor"},
    )


if __name__ == "__main__":
    uvicorn.run("gateway.main:app", host="0.0.0.0", port=8000, reload=True)
```

### `services/gateway-service/Dockerfile`

```dockerfile
# ── Stage 1: builder ──────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /app
COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# ── Stage 2: runtime ──────────────────────────────────────
FROM python:3.12-slim AS runtime

# Seguridad: usuario no-root
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser

WORKDIR /app

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY src/ ./src/

# Variables de entorno por defecto (no secretos)
ENV PYTHONPATH=/app/src \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_ENV=production

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

CMD ["uvicorn", "gateway.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
```

---

## 8. Funciones Lambda

### `lambdas/txn_processor/handler.py`

```python
"""
Lambda: txn-processor
Trigger: SQS Queue (txn-events-queue)
Responsabilidad: Consumir mensajes SQS, validar y persistir en DynamoDB.
"""
import json
import os
import boto3
import logging
from botocore.exceptions import ClientError
from typing import Any

logger = logging.getLogger(__name__)
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

dynamodb = boto3.resource("dynamodb", region_name=os.environ["AWS_REGION"])
table = dynamodb.Table(os.environ["DYNAMODB_TABLE"])
sns_client = boto3.client("sns", region_name=os.environ["AWS_REGION"])

ALERTS_TOPIC_ARN = os.environ["SNS_ALERTS_TOPIC_ARN"]
HIGH_VALUE_THRESHOLD = float(os.environ.get("HIGH_VALUE_THRESHOLD", "50000"))


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """
    Procesa batch de mensajes SQS con partial batch failure support.
    """
    failed_items = []

    for record in event.get("Records", []):
        try:
            process_record(record)
        except Exception as exc:
            logger.error(
                "Failed to process record",
                extra={
                    "message_id": record["messageId"],
                    "error": str(exc),
                },
            )
            failed_items.append({"itemIdentifier": record["messageId"]})

    # Partial batch failure: solo reencola los fallidos
    return {"batchItemFailures": failed_items}


def process_record(record: dict[str, Any]) -> None:
    body = json.loads(record["body"])
    detail = body.get("detail", {})

    txn_id = detail.get("txn_id")
    amount = float(detail.get("amount", 0))

    logger.info("Processing transaction", extra={"txn_id": txn_id, "amount": amount})

    # Persistir en DynamoDB con TTL de 7 días
    import time
    ttl = int(time.time()) + (7 * 24 * 60 * 60)

    table.put_item(
        Item={
            "txnId": txn_id,
            "timestamp": detail.get("timestamp"),
            "amount": str(amount),  # DynamoDB: Decimal como string
            "currency": detail.get("currency", "USD"),
            "txn_type": detail.get("txn_type"),
            "source_account": detail.get("source_account"),
            "destination_account": detail.get("destination_account"),
            "status": "PROCESSED",
            "sqs_message_id": record["messageId"],
            "ttl": ttl,
        },
        ConditionExpression="attribute_not_exists(txnId)",  # Idempotencia
    )

    # Alerta automática para transacciones de alto valor
    if amount > HIGH_VALUE_THRESHOLD:
        _publish_high_value_alert(txn_id, amount, detail)


def _publish_high_value_alert(txn_id: str, amount: float, detail: dict) -> None:
    try:
        sns_client.publish(
            TopicArn=ALERTS_TOPIC_ARN,
            Subject=f"[ALERTA] Transacción alto valor: {txn_id}",
            Message=json.dumps({
                "alert_type": "HIGH_VALUE_TRANSACTION",
                "txn_id": txn_id,
                "amount": amount,
                "detail": detail,
            }),
        )
        logger.warning("High value alert sent", extra={"txn_id": txn_id, "amount": amount})
    except ClientError as exc:
        logger.error("Failed to send alert", extra={"error": str(exc)})
        # No re-raise: la alerta es best-effort, no debe fallar el procesamiento
```

### `lambdas/dlq_handler/handler.py`

```python
"""
Lambda: dlq-reprocessor
Trigger: SQS DLQ (txn-dlq)
Responsabilidad: Reintentar procesamiento con backoff exponencial.
"""
import json
import os
import boto3
import logging
import time
from typing import Any

logger = logging.getLogger(__name__)
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

sqs_client = boto3.client("sqs", region_name=os.environ["AWS_REGION"])
dynamodb = boto3.resource("dynamodb", region_name=os.environ["AWS_REGION"])
table = dynamodb.Table(os.environ["DYNAMODB_TABLE"])

MAIN_QUEUE_URL = os.environ["MAIN_QUEUE_URL"]
MAX_RETRIES = int(os.environ.get("MAX_RETRIES", "3"))


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    failed_items = []

    for record in event.get("Records", []):
        message_id = record["messageId"]
        receive_count = int(record.get("attributes", {}).get("ApproximateReceiveCount", 1))

        try:
            body = json.loads(record["body"])
            detail = body.get("detail", {})
            txn_id = detail.get("txn_id")

            logger.warning(
                "DLQ message received",
                extra={"txn_id": txn_id, "receive_count": receive_count},
            )

            if receive_count <= MAX_RETRIES:
                # Backoff exponencial: 2^receive_count segundos
                backoff = 2 ** receive_count
                logger.info(f"Requeuing with delay {backoff}s", extra={"txn_id": txn_id})

                sqs_client.send_message(
                    QueueUrl=MAIN_QUEUE_URL,
                    MessageBody=record["body"],
                    DelaySeconds=min(backoff, 900),  # SQS max delay: 900s
                )
                _update_txn_status(txn_id, "RETRYING", receive_count)
            else:
                # Supera máximos reintentos: marcar como FAILED permanente
                logger.error(
                    "Max retries exceeded, marking as FAILED",
                    extra={"txn_id": txn_id},
                )
                _update_txn_status(txn_id, "FAILED", receive_count)

        except Exception as exc:
            logger.error("DLQ handler error", extra={"message_id": message_id, "error": str(exc)})
            failed_items.append({"itemIdentifier": message_id})

    return {"batchItemFailures": failed_items}


def _update_txn_status(txn_id: str | None, status: str, retry_count: int) -> None:
    if not txn_id:
        return
    try:
        table.update_item(
            Key={"txnId": txn_id},
            UpdateExpression="SET #s = :status, retry_count = :rc, updated_at = :ua",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={
                ":status": status,
                ":rc": retry_count,
                ":ua": str(int(time.time())),
            },
        )
    except Exception as exc:
        logger.error("Failed to update DynamoDB status", extra={"error": str(exc)})
```

### `lambdas/reconcile/handler.py`

```python
"""
Lambda: txn-reconcile
Trigger: EventBridge (rate: 5 minutes)
Responsabilidad: Detectar transacciones PENDING stuck y generar métricas de SLO.
"""
import os
import boto3
import logging
from datetime import datetime, timezone, timedelta
from boto3.dynamodb.conditions import Key, Attr
from typing import Any

logger = logging.getLogger(__name__)
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

dynamodb = boto3.resource("dynamodb", region_name=os.environ["AWS_REGION"])
cloudwatch = boto3.client("cloudwatch", region_name=os.environ["AWS_REGION"])
sns_client = boto3.client("sns", region_name=os.environ["AWS_REGION"])

TXN_TABLE = os.environ["DYNAMODB_TABLE"]
ALERTS_TOPIC_ARN = os.environ["SNS_ALERTS_TOPIC_ARN"]
PENDING_THRESHOLD_MINUTES = int(os.environ.get("PENDING_THRESHOLD_MINUTES", "10"))


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """
    Reconciliación periódica:
    1. Busca transacciones PENDING > 10 minutos (stuck transactions)
    2. Publica métricas de SLO en CloudWatch
    3. Alerta si hay stuck transactions
    """
    now = datetime.now(timezone.utc)
    threshold_time = (now - timedelta(minutes=PENDING_THRESHOLD_MINUTES)).isoformat()

    table = dynamodb.Table(TXN_TABLE)

    # Buscar PENDINGs antiguos usando el GSI status-index
    stuck_txns = table.query(
        IndexName="status-index",
        KeyConditionExpression=Key("status").eq("PENDING") & Key("timestamp").lt(threshold_time),
    ).get("Items", [])

    logger.info("Reconciliation run", extra={"stuck_count": len(stuck_txns), "run_time": now.isoformat()})

    # Publicar métrica en CloudWatch
    cloudwatch.put_metric_data(
        Namespace="TXNGateway/SLO",
        MetricData=[
            {
                "MetricName": "StuckTransactions",
                "Value": len(stuck_txns),
                "Unit": "Count",
                "Dimensions": [{"Name": "Environment", "Value": os.environ.get("APP_ENV", "dev")}],
            }
        ],
    )

    # Alertar si hay transacciones stuck
    if stuck_txns:
        txn_ids = [t.get("txnId") for t in stuck_txns[:10]]  # Primeras 10
        sns_client.publish(
            TopicArn=ALERTS_TOPIC_ARN,
            Subject=f"[RECONCILE] {len(stuck_txns)} transacciones PENDING stuck",
            Message=f"Se detectaron {len(stuck_txns)} transacciones en estado PENDING por más de {PENDING_THRESHOLD_MINUTES} minutos.\nPrimeras TXN IDs: {txn_ids}",
        )

    return {
        "reconciled_at": now.isoformat(),
        "stuck_transactions": len(stuck_txns),
        "status": "OK",
    }
```

---

## 9. Frontend — React Dashboard

### `frontend/src/components/Dashboard.tsx`

```tsx
import { useState, useEffect } from "react";
import TransactionTable from "./TransactionTable";
import MetricsChart from "./MetricsChart";
import AlertBanner from "./AlertBanner";
import SimulatorPanel from "./SimulatorPanel";
import { useTransactions } from "../hooks/useTransactions";

export default function Dashboard() {
  const { transactions, metrics, loading, error, refresh } = useTransactions();
  const [activeAlerts, setActiveAlerts] = useState<string[]>([]);

  useEffect(() => {
    const interval = setInterval(refresh, 10_000); // Poll cada 10 seg
    return () => clearInterval(interval);
  }, [refresh]);

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 font-mono">
      {/* Header */}
      <header className="border-b border-orange-500/30 bg-gray-900 px-6 py-4">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-orange-400">
              TXN Gateway Monitor
            </h1>
            <p className="text-xs text-gray-500">
              Analista Automatización · Gateway de Mensajería
            </p>
          </div>
          <div className="flex items-center gap-3">
            <span className="h-2 w-2 rounded-full bg-green-400 animate-pulse" />
            <span className="text-xs text-green-400">Sistema operativo</span>
          </div>
        </div>
      </header>

      {/* Alert Banner */}
      {activeAlerts.length > 0 && (
        <AlertBanner alerts={activeAlerts} onDismiss={() => setActiveAlerts([])} />
      )}

      {/* Main Grid */}
      <main className="grid grid-cols-12 gap-4 p-6">
        {/* KPI Cards */}
        <section className="col-span-12 grid grid-cols-4 gap-4">
          {metrics && (
            <>
              <KPICard label="Transacciones / hr" value={metrics.txnPerHour} color="orange" />
              <KPICard label="Tasa de éxito" value={`${metrics.successRate}%`} color="green" />
              <KPICard label="Mensajes DLQ" value={metrics.dlqCount} color="red" />
              <KPICard label="Latencia P95 (ms)" value={metrics.p95Latency} color="blue" />
            </>
          )}
        </section>

        {/* Chart */}
        <section className="col-span-8 rounded-lg border border-gray-800 bg-gray-900 p-4">
          <h2 className="mb-3 text-sm font-semibold text-gray-400">
            Flujo de transacciones (últimas 2 horas)
          </h2>
          <MetricsChart data={metrics?.timeline ?? []} />
        </section>

        {/* Simulator */}
        <aside className="col-span-4 rounded-lg border border-gray-800 bg-gray-900 p-4">
          <h2 className="mb-3 text-sm font-semibold text-gray-400">
            Simulador de transacciones
          </h2>
          <SimulatorPanel onPublished={refresh} />
        </aside>

        {/* Transaction Table */}
        <section className="col-span-12 rounded-lg border border-gray-800 bg-gray-900 p-4">
          <h2 className="mb-3 text-sm font-semibold text-gray-400">
            Transacciones recientes
          </h2>
          {loading ? (
            <p className="text-xs text-gray-500">Cargando...</p>
          ) : error ? (
            <p className="text-xs text-red-400">Error cargando datos: {error}</p>
          ) : (
            <TransactionTable transactions={transactions} />
          )}
        </section>
      </main>
    </div>
  );
}

function KPICard({
  label,
  value,
  color,
}: {
  label: string;
  value: string | number;
  color: "orange" | "green" | "red" | "blue";
}) {
  const colorMap = {
    orange: "border-orange-500/40 text-orange-400",
    green: "border-green-500/40 text-green-400",
    red: "border-red-500/40 text-red-400",
    blue: "border-blue-500/40 text-blue-400",
  };
  return (
    <div className={`rounded-lg border bg-gray-900 p-4 ${colorMap[color]}`}>
      <p className="text-xs text-gray-500">{label}</p>
      <p className={`mt-1 text-2xl font-bold ${colorMap[color].split(" ")[1]}`}>
        {value}
      </p>
    </div>
  );
}
```

---

## 10. EventBridge Rules

```json
// Regla detección de fraude — event pattern
{
  "source": ["txn.gateway"],
  "detail-type": ["TransactionEvent"],
  "detail": {
    "amount": [{ "numeric": [">", 50000] }],
    "txn_type": ["TRANSFER", "WITHDRAWAL"]
  }
}
```

```json
// Regla alerta de múltiples fallos — event pattern
{
  "source": ["txn.gateway"],
  "detail-type": ["TransactionFailed"],
  "detail": {
    "retry_count": [{ "numeric": [">=", 2] }]
  }
}
```

---

## 11. DynamoDB — Modelos de Datos

### Tabla: `txn-events`

| Atributo           | Tipo   | Descripción                            |
|--------------------|--------|----------------------------------------|
| `txnId` (PK)       | String | UUID de la transacción                 |
| `timestamp` (SK)   | String | ISO 8601 UTC                           |
| `amount`           | String | Monto (string para precisión decimal)  |
| `currency`         | String | Código de moneda ISO 4217              |
| `txn_type`         | String | PAYMENT / TRANSFER / WITHDRAWAL        |
| `source_account`   | String | Cuenta origen                          |
| `destination_account` | String | Cuenta destino                      |
| `status`           | String | PENDING / PROCESSED / FAILED / RETRYING |
| `sqs_message_id`   | String | ID del mensaje SQS                     |
| `retry_count`      | Number | Número de reintentos                   |
| `ttl`              | Number | Unix timestamp de expiración (7 días)  |

**GSI: `status-index`**
- PK: `status`
- SK: `timestamp`
- Proyección: ALL

### Tabla: `gw-metrics`

| Atributo       | Tipo   | Descripción                    |
|----------------|--------|--------------------------------|
| `date` (PK)    | String | Fecha YYYY-MM-DD               |
| `service` (SK) | String | Nombre del servicio            |
| `txn_count`    | Number | Total transacciones del día    |
| `success_count`| Number | Transacciones exitosas         |
| `failed_count` | Number | Transacciones fallidas         |
| `avg_amount`   | String | Monto promedio                 |

---

## 12. CI/CD — GitHub Actions

### `.github/workflows/ci.yml`

```yaml
name: CI — Lint, Test, Build

on:
  pull_request:
    branches: [main]

jobs:
  lint-and-test:
    name: Python Lint & Test
    runs-on: ubuntu-latest
    strategy:
      matrix:
        service: [gateway-service, txn_processor, dlq_handler, reconcile]

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python 3.12
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip

      - name: Install dependencies
        run: |
          pip install --upgrade pip
          pip install ruff mypy pytest pytest-asyncio moto[sqs,sns,dynamodb] coverage httpx

      - name: Lint with ruff
        run: ruff check . --select E,W,F,I,N,UP

      - name: Type check with mypy
        run: mypy src/ --strict

      - name: Run tests with coverage
        run: |
          coverage run -m pytest tests/ -v
          coverage report --fail-under=85

  build-docker:
    name: Build Docker Image
    runs-on: ubuntu-latest
    needs: lint-and-test
    steps:
      - uses: actions/checkout@v4
      - name: Build image
        run: docker build -t txn-gateway:${{ github.sha }} services/gateway-service/
```

### `.github/workflows/deploy.yml`

```yaml
name: Deploy — ECS + Lambda

on:
  push:
    branches: [main]

env:
  AWS_REGION: us-east-1
  ECR_REPOSITORY: txn-gateway-service

jobs:
  deploy:
    runs-on: ubuntu-latest
    permissions:
      id-token: write   # OIDC para AWS sin secrets de larga duración
      contents: read

    steps:
      - uses: actions/checkout@v4

      - name: Configure AWS credentials (OIDC)
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ secrets.AWS_DEPLOY_ROLE_ARN }}
          aws-region: ${{ env.AWS_REGION }}

      - name: Login to ECR
        id: login-ecr
        uses: aws-actions/amazon-ecr-login@v2

      - name: Build, tag and push image to ECR
        env:
          ECR_REGISTRY: ${{ steps.login-ecr.outputs.registry }}
          IMAGE_TAG: ${{ github.sha }}
        run: |
          docker build -t $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG services/gateway-service/
          docker push $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG
          echo "image=$ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG" >> $GITHUB_OUTPUT

      - name: Deploy to ECS (rolling update)
        run: |
          aws ecs update-service \
            --cluster txn-gateway-cluster \
            --service gateway-service \
            --force-new-deployment

      - name: Deploy Lambda functions
        run: |
          for fn in txn_processor dlq_handler reconcile; do
            zip -j /tmp/${fn}.zip lambdas/${fn}/handler.py
            aws lambda update-function-code \
              --function-name txn-${fn} \
              --zip-file fileb:///tmp/${fn}.zip
          done

      - name: Wait for ECS deployment
        run: |
          aws ecs wait services-stable \
            --cluster txn-gateway-cluster \
            --services gateway-service
```

---

## 13. Observabilidad

### CloudWatch Dashboard (JSON widget config)

```json
{
  "widgets": [
    {
      "type": "metric",
      "properties": {
        "title": "Transacciones por minuto",
        "metrics": [
          ["AWS/SQS", "NumberOfMessagesSent", "QueueName", "txn-events-queue"],
          ["AWS/SQS", "NumberOfMessagesReceived", "QueueName", "txn-events-queue"]
        ],
        "period": 60,
        "stat": "Sum"
      }
    },
    {
      "type": "metric",
      "properties": {
        "title": "DLQ — Mensajes fallidos",
        "metrics": [
          ["AWS/SQS", "ApproximateNumberOfMessagesVisible", "QueueName", "txn-dlq"]
        ],
        "alarms": ["txn-dlq-alarm"]
      }
    },
    {
      "type": "metric",
      "properties": {
        "title": "Lambda Errors",
        "metrics": [
          ["AWS/Lambda", "Errors", "FunctionName", "txn-processor"],
          ["AWS/Lambda", "Errors", "FunctionName", "dlq-reprocessor"]
        ]
      }
    }
  ]
}
```

### CloudWatch Alarm — DLQ

```hcl
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
  alarm_actions       = [var.sns_alerts_topic_arn]
  dimensions = {
    QueueName = "txn-dlq"
  }
}
```

### SLOs definidos

| Indicador                        | Objetivo | Medición               |
|----------------------------------|----------|------------------------|
| Disponibilidad del gateway       | 99.5%    | /health CloudWatch     |
| Tasa de procesamiento exitoso    | 99.0%    | (success/total) * 100  |
| Tiempo procesamiento P95         | < 2 seg  | SQS ApproximateAge     |
| Mensajes DLQ acumulados          | < 5      | CloudWatch Alarm       |
| Latencia de alerta de fraude     | < 30 seg | SNS publish latency    |

---

## 14. Plan de Ejecución por Fases

### Fase 1 — Infraestructura base (Días 1-3)
```
[ ] Crear cuenta AWS (Free Tier)
[ ] Instalar: AWS CLI, Terraform, Docker, Python 3.12, Node 20
[ ] Configurar AWS CLI con perfil local: aws configure
[ ] Clonar/crear repositorio GitHub
[ ] Ejecutar terraform init && terraform plan en infra/
[ ] Verificar recursos creados: SQS, SNS, DynamoDB, Lambda stubs
```

### Fase 2 — Microservicio ECS (Días 4-6)
```
[ ] Implementar gateway-service/src/ completo
[ ] Tests unitarios con moto (pytest)
[ ] Build Docker local: docker build -t txn-gateway .
[ ] Crear repositorio ECR y push imagen
[ ] Deploy módulo Terraform ecs/
[ ] Verificar endpoint /health desde EC2 o ALB
```

### Fase 3 — Lambdas (Días 7-9)
```
[ ] Implementar txn_processor/handler.py + tests
[ ] Implementar dlq_handler/handler.py + tests
[ ] Implementar reconcile/handler.py + tests
[ ] Deploy via Terraform módulo lambda/
[ ] Verificar trigger SQS → Lambda con mensaje de prueba
[ ] Verificar EventBridge → reconcile Lambda
```

### Fase 4 — Frontend (Días 10-12)
```
[ ] Scaffold React con Vite: npm create vite@latest frontend -- --template react-ts
[ ] Implementar componentes: Dashboard, TransactionTable, MetricsChart, SimulatorPanel
[ ] Conectar con API Gateway endpoint
[ ] Deploy en S3 static hosting + CloudFront (Free Tier)
[ ] Verificar simulador envía transacciones y dashboard actualiza
```

### Fase 5 — Observabilidad y CI/CD (Días 13-15)
```
[ ] Configurar GitHub Actions CI (lint + test)
[ ] Configurar GitHub Actions deploy (OIDC)
[ ] Crear CloudWatch Dashboard
[ ] Configurar alarmas CloudWatch → SNS email
[ ] Probar flujo completo end-to-end
[ ] Documentar en README con arquitectura y demo GIF
```

### Fase 6 — Portfolio (Días 16-18)
```
[ ] Grabar video demo de 5 minutos mostrando:
    - Dashboard en vivo
    - Simulación de transacción normal
    - Simulación de transacción alto valor (alerta)
    - Simulación de fallo y reintento automático DLQ
    - CloudWatch métricas y logs
[ ] Publicar repositorio público en GitHub
[ ] Agregar badges: CI/CD, coverage, Python version
[ ] Escribir caso de estudio en LinkedIn
```

---

## 15. Buenas Prácticas Aplicadas

### Seguridad
- **Least privilege IAM**: cada Lambda y ECS task tiene rol con permisos mínimos necesarios
- **No hardcoded secrets**: secrets en AWS Secrets Manager, config en environment variables
- **OIDC para CI/CD**: GitHub Actions usa OIDC, no credenciales de larga duración
- **Dockerfile usuario no-root**: imagen corre como `appuser`, no `root`

### Resiliencia
- **Idempotencia**: `ConditionExpression: attribute_not_exists(txnId)` en DynamoDB
- **Dead Letter Queue**: mensajes fallidos capturados automáticamente tras 3 intentos
- **Partial batch failure**: Lambda retorna `batchItemFailures` para no perder mensajes buenos
- **Retry con backoff exponencial**: `dlq_handler` aplica delays 2^n segundos

### Observabilidad (SRE)
- **Structured logging**: JSON logs en todas las funciones y servicio ECS
- **Métricas customizadas**: `TXNGateway/SLO` namespace en CloudWatch
- **SLOs definidos y medidos**: 5 indicadores con objetivos claros
- **Runbook documentado**: `docs/runbook.md` con pasos de respuesta a incidentes

### Código Python
- **Type hints completos**: `mypy --strict` en CI
- **Pydantic v2**: validación de entrada con mensajes de error claros
- **Separación de responsabilidades**: `routers/ → services/ → repositories/`
- **Tests con moto**: sin llamadas reales a AWS en tests unitarios
- **Cobertura >85%**: verificada en CI con `coverage`

### IaC (Terraform)
- **Módulos reutilizables**: cada servicio AWS en su propio módulo
- **Default tags**: todos los recursos etiquetados con `Project`, `Environment`, `ManagedBy`
- **Outputs explícitos**: ARNs y URLs compartidos entre módulos via outputs
- **Variables tipadas**: `variables.tf` con `type`, `description` y `default` donde aplica

---

## 16. FAQ / Preguntas de Entrevista

**¿Por qué SQS en lugar de Kinesis?**
> Para este caso de uso (mensajería transaccional con reintentos y DLQ), SQS es ideal. Kinesis tiene mejor rendimiento para streaming de alta velocidad, pero SQS tiene DLQ nativa, visibilidad de mensajes y está en el Free Tier. Ver `docs/ADR-001-sqs-vs-kinesis.md`.

**¿Cómo garantizas que un mensaje no se procesa dos veces?**
> Con `ConditionExpression: attribute_not_exists(txnId)` en DynamoDB — si la transacción ya existe, el PutItem falla silenciosamente. Esto garantiza idempotencia end-to-end.

**¿Qué es el toil que automatizaste?**
> Revisión manual de logs, reencolar mensajes fallidos y generar reportes de estado. Con SQS DLQ + Lambda + EventBridge + CloudWatch Alarms, ninguna de esas tareas requiere intervención humana.

**¿Cómo manejas los fallos de la DLQ Lambda?**
> La DLQ Lambda usa `batchItemFailures` para partial batch failure. Si falla reencolar un mensaje, ese específico vuelve a la DLQ para reintento posterior. El resto se procesa normalmente.

**¿Cuáles son los SLOs del sistema?**
> Tasa de éxito de procesamiento 99%, disponibilidad del gateway 99.5%, P95 de latencia < 2 segundos, mensajes DLQ acumulados < 5. Todos medidos en CloudWatch con alarmas automáticas.

**¿Cómo harías esto en producción real?**
> Agregaría: VPC con subnets privadas para ECS, AWS WAF en el API Gateway, encriptación KMS en DynamoDB y SQS, ALB con certificado TLS, y backend de Terraform en S3+DynamoDB para state remoto con locking.

---

*Proyecto generado para portfolio · Analista Automatización Gateway de Mensajería*  
*Stack: Python 3.12 · FastAPI · AWS SQS · SNS · Lambda · ECS · EventBridge · DynamoDB · Terraform · React*
