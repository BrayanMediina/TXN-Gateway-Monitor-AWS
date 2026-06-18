# TXN Gateway Monitor — Documentación Técnica Completa

## Tabla de Contenidos

1. [¿Qué es esta aplicación?](#1-qué-es-esta-aplicación)
2. [Arquitectura general](#2-arquitectura-general)
3. [Flujo de datos end-to-end](#3-flujo-de-datos-end-to-end)
4. [Estructura de carpetas](#4-estructura-de-carpetas)
5. [Componentes en la nube (AWS)](#5-componentes-en-la-nube-aws)
6. [Direccionamiento y networking](#6-direccionamiento-y-networking)
7. [Gestión de identidad y acceso (IAM)](#7-gestión-de-identidad-y-acceso-iam)
8. [CI/CD — GitHub Actions](#8-cicd--github-actions)
9. [Observabilidad](#9-observabilidad)
10. [Seguridad — hallazgos y estado](#10-seguridad--hallazgos-y-estado)

---

## 1. ¿Qué es esta aplicación?

**TXN Gateway Monitor** es un sistema de procesamiento de transacciones financieras con monitoreo en tiempo real. Simula la capa de mensajería de una pasarela de pagos: recibe eventos de transacciones (pagos, transferencias, retiros, depósitos), los procesa de forma asíncrona con reintentos automáticos y expone métricas operacionales en un dashboard web.

**Caso de uso:** Demuestra patrones de arquitectura cloud que se usan en producción en fintechs y bancos digitales: event-driven, retry con dead-letter queue, reconciliación periódica, alertas automáticas e infraestructura como código completa.

---

## 2. Arquitectura general

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              USUARIO                                    │
└──────────────────────┬──────────────────────────────────────────────────┘
                       │ HTTPS
           ┌───────────▼───────────┐
           │   CloudFront CDN      │  https://d3q5sjqh5x3d32.cloudfront.net
           │   (React SPA)         │  S3: txn-gateway-frontend-709147558620
           └───────────┬───────────┘
                       │ HTTPS (axios)
           ┌───────────▼───────────┐
           │   API Gateway V2      │  https://xkokv2ttg8.execute-api.us-east-1.amazonaws.com
           │   (HTTP proxy)        │  ANY /{proxy+} → ECS :8000
           └───────────┬───────────┘
                       │ HTTP :8000
           ┌───────────▼───────────┐
           │   ECS Fargate         │  txn-gateway-cluster / gateway-service
           │   FastAPI + uvicorn   │  256 CPU / 512 MB / Python 3.12
           └──┬──────────┬─────────┘
              │          │
     ┌────────▼──┐  ┌────▼──────────────┐
     │  DynamoDB │  │       SNS          │
     │ txn-events│  │ txn-gateway-topic  │
     └───────────┘  └────────┬───────────┘
                             │ Suscripción SQS
                   ┌─────────▼──────────────┐
                   │     SQS Queue           │
                   │   txn-events-queue      │
                   │   (maxReceive: 3)       │
                   └────────┬───────────────┘
                            │ Trigger
                   ┌────────▼───────────┐       ┌─────────────────────┐
                   │  Lambda            │──────►│  DynamoDB           │
                   │  txn-processor     │       │  txn-events         │
                   └────────────────────┘       └─────────────────────┘
                            │ (tras 3 fallos)
                   ┌────────▼───────────┐
                   │   SQS DLQ          │
                   │   txn-dlq          │
                   └────────┬───────────┘
                            │ Trigger
                   ┌────────▼───────────┐
                   │  Lambda            │  backoff exponencial
                   │  dlq-reprocessor   │  reencola a txn-events-queue
                   └────────────────────┘

           ┌─────────────────────────────────────┐
           │  EventBridge (rate: 5 min)           │
           └──────────────┬──────────────────────┘
                          │
                 ┌────────▼──────────┐
                 │  Lambda           │  Detecta PENDING > 10 min
                 │  txn-reconcile    │  Publica métrica CloudWatch SLO
                 └────────┬──────────┘
                          │ Si hay stuck txns
                 ┌────────▼──────────┐
                 │  SNS Alerts       │  txn-alerts-topic → email
                 └───────────────────┘
```

---

## 3. Flujo de datos end-to-end

### Flujo feliz (transacción exitosa)

```
1. Usuario hace POST /events/publish desde el dashboard
   Body: { txn_id, amount, txn_type, source_account, destination_account }

2. ECS (FastAPI):
   a. Valida el payload con Pydantic
   b. Guarda en DynamoDB con status=PENDING
   c. Publica en SNS txn-gateway-topic
   d. Actualiza DynamoDB a status=PROCESSED
   e. Retorna 202 Accepted

3. SNS entrega el mensaje a SQS txn-events-queue

4. Lambda txn-processor consume el batch de SQS:
   a. Parsea el mensaje
   b. Hace put_item en DynamoDB con status=PROCESSED
   c. Si amount > 50.000: publica alerta a SNS txn-alerts-topic
   d. Retorna batchItemFailures=[] (éxito total)

5. DynamoDB tiene el registro con TTL de 7 días
```

### Flujo de error (con reintentos)

```
1. txn-processor falla al procesar un mensaje
   → SQS incrementa ApproximateReceiveCount
   → A los 3 fallos: mueve el mensaje a txn-dlq

2. Lambda dlq-reprocessor consume de txn-dlq:
   - Si receive_count ≤ 3: reencola a txn-events-queue con delay 2^n segundos
     Actualiza DynamoDB → RETRYING
   - Si receive_count > 3: marca permanente como FAILED en DynamoDB

3. txn-reconcile (cada 5 min):
   - Consulta GSI status-index filtrando PENDING con timestamp < now-10min
   - Si encuentra transacciones stuck: publica alerta SNS → email
   - Siempre publica métrica TXNGateway/SLO::StuckTransactions en CloudWatch
```

---

## 4. Estructura de carpetas

```
TXN-Gateway-Monitor-AWS/
│
├── .github/
│   └── workflows/
│       ├── ci.yml          # Lint + test en Pull Request
│       └── deploy.yml      # Build + deploy en push a main
│
├── docs/
│   ├── ARQUITECTURA.md     # Este documento
│   ├── ADR-001-sqs-vs-kinesis.md
│   ├── ADR-002-fastapi-vs-flask.md
│   └── runbook.md
│
├── frontend/               # React SPA (Vite + TypeScript + Tailwind)
│   ├── src/
│   │   ├── components/     # Dashboard, TransactionTable, MetricsChart,
│   │   │                   # AlertBanner, SimulatorPanel
│   │   ├── hooks/          # useTransactions (polling cada 5s)
│   │   ├── services/
│   │   │   └── api.ts      # axios client, tipos TypeScript
│   │   ├── main.tsx        # Punto de entrada React
│   │   └── index.css       # Tailwind base/components/utilities
│   ├── .env.local          # VITE_API_URL=http://localhost:8000 (gitignored)
│   ├── .env.production     # VITE_API_URL=https://xkokv2ttg8...amazonaws.com
│   ├── postcss.config.js   # Habilita Tailwind + autoprefixer
│   ├── tailwind.config.ts  # Content scan para JIT
│   └── vite.config.ts      # Dev proxy /api → backend
│
├── infra/                  # Terraform IaC completa
│   ├── main.tf             # Módulos + OIDC + CloudWatch + IAM GitHub Actions
│   ├── variables.tf        # Declaración de variables
│   ├── terraform.tfvars    # Valores concretos (gitignored)
│   └── modules/
│       ├── apigw/          # API Gateway V2 HTTP API
│       ├── dynamodb/       # Tabla txn-events + GSI status-index
│       ├── ecs/            # Cluster + Task Definition + Service + SG + IAM
│       ├── eventbridge/    # Regla txn-reconcile-schedule (rate 5 min)
│       ├── frontend/       # S3 bucket + CloudFront + OAC + bucket policy
│       ├── lambda/         # 3 funciones + IAM role + event source mappings
│       ├── sns/            # txn-gateway-topic + txn-alerts-topic + suscripción email
│       └── sqs/            # txn-events-queue + txn-dlq + redrive policy
│
├── lambdas/
│   ├── txn_processor/
│   │   ├── handler.py      # Consume SQS, persiste en DynamoDB, alerta alto valor
│   │   ├── requirements.txt
│   │   └── tests/
│   ├── dlq_handler/
│   │   ├── handler.py      # Backoff exponencial, reencola o marca FAILED
│   │   ├── requirements.txt
│   │   └── tests/
│   └── reconcile/
│       ├── handler.py      # Detecta stuck txns, métrica CloudWatch, alerta SNS
│       ├── requirements.txt
│       └── tests/
│
├── scripts/
│   ├── seed_dynamodb.py    # Inserta datos de prueba en DynamoDB
│   ├── simulate_events.py  # Envía transacciones al gateway en loop
│   └── check_health.sh     # Curl al /health endpoint
│
└── services/
    └── gateway-service/    # Microservicio FastAPI (ECS)
        ├── Dockerfile
        ├── pyproject.toml
        ├── requirements.txt
        ├── requirements-dev.txt
        └── src/gateway/
            ├── config.py           # Pydantic Settings (env vars)
            ├── main.py             # FastAPI app, CORS, routers, lifespan
            ├── models/
            │   └── transaction.py  # TransactionEvent, TransactionResponse (Pydantic)
            ├── routers/
            │   ├── events.py       # POST /events/publish, GET /events, GET /events/{id}
            │   ├── health.py       # GET /health
            │   └── metrics.py      # GET /metrics (DynamoDB + SQS DLQ)
            ├── services/
            │   ├── dynamodb_service.py  # CRUD + scan + métricas desde DynamoDB
            │   └── sns_service.py       # Publish a SNS
            ├── repositories/
            │   └── txn_repository.py    # Abstracción repositorio
            ├── middleware/
            │   └── logging.py      # structlog JSON structured logging
            └── exceptions/
                └── handlers.py     # DynamoDBError, SNSError
```

---

## 5. Componentes en la nube (AWS)

### 5.1 Frontend — S3 + CloudFront

| Recurso | Nombre / ID |
|---------|-------------|
| S3 Bucket | `txn-gateway-frontend-709147558620` |
| CloudFront Distribution | `E262ESWDTB9GPB` |
| URL pública | `https://d3q5sjqh5x3d32.cloudfront.net` |

**Cómo funciona:**
- El bucket S3 está **completamente privado** (public access block activado en los 4 ajustes)
- CloudFront accede al bucket mediante **Origin Access Control (OAC)** — el único principal autorizado en la bucket policy es `cloudfront.amazonaws.com` con condición `AWS:SourceArn = arn:...:distribution/E262ESWDTB9GPB`
- Los errores 404 y 403 se redirigen a `/index.html` con código 200 para que React Router funcione (SPA routing)
- El build de Vite produce 3 archivos: `index.html`, `assets/index-*.css` (~10 KB Tailwind procesado), `assets/index-*.js` (~583 KB bundle)
- La variable `VITE_API_URL` se inyecta desde `frontend/.env.production` en tiempo de build. Apunta al API Gateway HTTPS, resolviendo el problema de Mixed Content

### 5.2 API Gateway V2 — Proxy HTTPS → ECS

| Recurso | Valor |
|---------|-------|
| API ID | `xkokv2ttg8` |
| Tipo | HTTP API (v2) |
| URL estable | `https://xkokv2ttg8.execute-api.us-east-1.amazonaws.com` |
| Integration ID | `hoihcu6` |

**Cómo funciona:**
- Route `ANY /{proxy+}` → integración `HTTP_PROXY` → `http://<ECS-IP>:8000/{proxy}`
- El deploy workflow obtiene la IP actual del task ECS y actualiza la `integration_uri` en cada push
- CORS configurado en API GW para permitir `https://d3q5sjqh5x3d32.cloudfront.net`
- **Por qué es necesario:** CloudFront sirve el frontend en HTTPS. El browser bloquea peticiones HTTP desde una página HTTPS (Mixed Content). API Gateway provee un endpoint HTTPS estable aunque la IP de ECS cambie en cada despliegue

### 5.3 ECS Fargate — Gateway Service

| Recurso | Valor |
|---------|-------|
| Cluster | `txn-gateway-cluster` |
| Service | `gateway-service` |
| Task Definition family | `gateway-service` |
| CPU / Memory | 256 vCPU / 512 MB |
| Puerto | 8000 |
| ECR Repository | `709147558620.dkr.ecr.us-east-1.amazonaws.com/txn-gateway-service` |

**Cómo funciona:**
- ECS ejecuta el contenedor Docker construido desde `services/gateway-service/Dockerfile`
- El container corre `uvicorn gateway.main:app --host 0.0.0.0 --port 8000`
- Las variables de entorno se inyectan en la Task Definition (no en el código):
  - `DYNAMODB_TXN_TABLE=txn-events`
  - `SNS_GATEWAY_TOPIC_ARN=arn:...:txn-gateway-topic`
  - `SNS_ALERTS_TOPIC_ARN=arn:...:txn-alerts-topic`
- Health check: `python -c "urllib.request.urlopen('http://localhost:8000/health')"` cada 30s
- El lifecycle `ignore_changes = [task_definition]` evita que Terraform revierta el task definition que actualiza el deploy workflow

**Endpoints:**
```
GET  /health              → Estado del servicio
POST /events/publish      → Publica transacción (guarda en DynamoDB + SNS)
GET  /events?limit=N      → Lista últimas N transacciones (scan DynamoDB)
GET  /events/{txn_id}     → Consulta transacción por ID (query por PK)
GET  /metrics             → KPIs del dashboard (status counts + DLQ + timeline)
```

### 5.4 DynamoDB — txn-events

| Atributo | Valor |
|----------|-------|
| Tabla | `txn-events` |
| Partition Key | `txnId` (String) |
| Sort Key | `timestamp` (String, ISO 8601 UTC) |
| GSI | `status-index`: PK=`status`, SK=`timestamp` |
| TTL | Atributo `ttl` (epoch seconds + 7 días) |
| Billing | PAY_PER_REQUEST |

**Por qué clave compuesta (txnId + timestamp):**
Una misma transacción puede tener múltiples registros con distintos timestamps si se reintenta. El sort key `timestamp` permite consultar todos los intentos de una transacción y ordenarlos cronológicamente.

**Por qué el GSI status-index:**
Las queries más frecuentes del dashboard son por estado (`WHERE status = 'PROCESSED'`). DynamoDB no permite filtrar eficientemente por atributos no-clave sin un GSI. El GSI `status-index` con SK=`timestamp` permite consultar transacciones por estado y rango de tiempo en O(log n) en lugar de hacer un scan completo.

### 5.5 SQS — Cola principal + DLQ

| Cola | URL | Propósito |
|------|-----|-----------|
| `txn-events-queue` | `.../txn-events-queue` | Mensajes para procesar |
| `txn-dlq` | `.../txn-dlq` | Mensajes que fallaron 3 veces |

**Configuración:**
- `visibility_timeout = 30s` — el message está bloqueado 30s mientras Lambda lo procesa
- `maxReceiveCount = 3` — tras 3 fallos se mueve automáticamente a la DLQ
- La DLQ trigger activa `dlq-reprocessor` que reencola con backoff exponencial (`DelaySeconds = min(2^n, 900)`)

### 5.6 SNS — Tópicos de mensajería

| Tópico | ARN | Uso |
|--------|-----|-----|
| `txn-gateway-topic` | `arn:...:txn-gateway-topic` | ECS publica eventos de transacciones → SQS los consume |
| `txn-alerts-topic` | `arn:...:txn-alerts-topic` | Alertas operacionales → suscripción email |

**Suscripciones configuradas:**
- `txn-gateway-topic` → `txn-events-queue` (protocolo SQS): el gateway service publica aquí y la cola los entrega a la Lambda
- `txn-alerts-topic` → email `julianmedinadev@gmail.com`: recibe alertas de alto valor y stuck transactions

### 5.7 Lambda Functions

#### `txn-processor` — Procesador principal
- **Trigger:** SQS `txn-events-queue` (batch de 10 mensajes)
- **Runtime:** Python 3.12, 256 MB
- **Lógica:**
  1. Parsea el body del mensaje SQS (viene de SNS → SQS)
  2. `put_item` en DynamoDB con `ConditionExpression="attribute_not_exists(txnId)"` — **idempotencia**: si el item ya existe (retry), no lo sobreescribe
  3. Si `amount > HIGH_VALUE_THRESHOLD (50.000)`: publica alerta a SNS
  4. Retorna `batchItemFailures` para que SQS solo reencole los mensajes que fallaron, no el batch completo

#### `dlq-reprocessor` — Manejador de errores
- **Trigger:** SQS `txn-dlq` (batch de 5 mensajes)
- **Runtime:** Python 3.12, 256 MB
- **Lógica:**
  1. Lee `ApproximateReceiveCount` del mensaje
  2. Si ≤ 3 reintentos: reencola a `txn-events-queue` con `DelaySeconds = min(2^n, 900)`
  3. Si > 3 reintentos: actualiza DynamoDB a `FAILED` permanente
  4. En ambos casos actualiza el estado en DynamoDB con clave compuesta `{txnId, timestamp}`

#### `txn-reconcile` — Reconciliador periódico
- **Trigger:** EventBridge rule `txn-reconcile-schedule` cada 5 minutos
- **Runtime:** Python 3.12, 256 MB
- **Lógica:**
  1. Consulta GSI `status-index` buscando items con `status=PENDING` y `timestamp < now-10min`
  2. Publica métrica `TXNGateway/SLO::StuckTransactions` a CloudWatch
  3. Si hay stuck transactions: publica alerta a `txn-alerts-topic`

---

## 6. Direccionamiento y networking

### 6.1 VPC y subnets

El proyecto usa la **Default VPC** de us-east-1. ECS Fargate corre en subnets públicas con IP pública asignada (`assign_public_ip = true`). En producción se usaría:
- Subnets privadas para ECS
- NAT Gateway para salida a internet
- API Gateway VPC Link para entrada (elimina la IP pública del task)

### 6.2 Flujo de red completo

```
Browser (HTTPS 443)
  └─► CloudFront Edge (*.cloudfront.net)
        └─► S3 Origin (private, OAC)   → Sirve index.html / assets

Browser API call (HTTPS 443)
  └─► API Gateway (execute-api.us-east-1.amazonaws.com)
        └─► ECS Task IP :8000 (HTTP)   → FastAPI procesa la request
              ├─► DynamoDB (AWS SDK, HTTPS internamente)
              └─► SNS (AWS SDK, HTTPS internamente)
                    └─► SQS (suscripción) → Lambda (event source mapping)
                          └─► DynamoDB (HTTPS)
```

### 6.3 Security Group de ECS (`txn-gateway-sg`)

| Dirección | Puerto | Protocolo | Origen | Nota |
|-----------|--------|-----------|--------|------|
| Ingress | 8000 | TCP | 0.0.0.0/0 | Necesario para API GW (mejora: VPC Link) |
| Egress | All | All | 0.0.0.0/0 | SDK calls a DynamoDB/SNS/SQS |

### 6.4 Por qué la IP de ECS cambia

ECS Fargate asigna IPs dinámicamente desde el rango de la subnet. Cada `force-new-deployment` crea un nuevo task con nueva ENI y nueva IP pública. Por eso el deploy workflow, después de que el servicio estabiliza, consulta la IP del nuevo task y actualiza la `integration_uri` de API Gateway. La URL de API GW permanece constante; solo la IP de destino del proxy cambia.

---

## 7. Gestión de identidad y acceso (IAM)

El proyecto usa **5 IAM roles** y **sigue el principio de mínimo privilegio** en cada uno.

### 7.1 Resumen de roles

| Role | Quién lo asume | Propósito |
|------|---------------|-----------|
| `txn-gateway-ecs-execution-role` | `ecs-tasks.amazonaws.com` | ECS pull imagen ECR + enviar logs a CloudWatch |
| `txn-gateway-ecs-task-role` | `ecs-tasks.amazonaws.com` | El código de la app: DynamoDB, SNS, SQS, X-Ray |
| `txn-gateway-lambda-role` *(en módulo lambda)* | `lambda.amazonaws.com` | Las 3 Lambdas: DynamoDB, SQS, SNS, CloudWatch, logs |
| `txn-gateway-github-actions-role` | GitHub OIDC | CI/CD: ECR, ECS, Lambda, S3, CloudFront, API GW |
| IAM de EventBridge | `events.amazonaws.com` | Invocar la Lambda de reconciliación |

---

### 7.2 ECS Execution Role — `txn-gateway-ecs-execution-role`

**Quién lo usa:** El agente de ECS (no el código de la app). Se usa para arrancar el container.

**Políticas:**
- `AmazonECSTaskExecutionRolePolicy` (managed policy de AWS)
  - `ecr:GetAuthorizationToken` — obtener token para descargar imagen del ECR
  - `ecr:BatchCheckLayerAvailability`, `ecr:GetDownloadUrlForLayer`, `ecr:BatchGetImage` — pull de la imagen Docker
  - `logs:CreateLogStream`, `logs:PutLogEvents` — enviar stdout/stderr del container a CloudWatch

**Por qué separado del task role:** El execution role es para operaciones de infraestructura (pull image, logs). El task role es para lo que ejecuta el código. Separación de responsabilidades.

---

### 7.3 ECS Task Role — `txn-gateway-ecs-task-role`

**Quién lo usa:** El proceso Python dentro del container (boto3 SDK).

**Permisos otorgados:**

```
DynamoDB:
  - PutItem, GetItem, UpdateItem, Query, Scan
  Resource: arn:aws:dynamodb:us-east-1:709147558620:table/txn-events
            arn:aws:dynamodb:us-east-1:709147558620:table/txn-events/index/*
  Razón: Guardar/consultar transacciones y el GSI status-index

SNS Publish:
  - sns:Publish
  Resource: arn:...:txn-gateway-topic
            arn:...:txn-alerts-topic
  Razón: Publicar eventos y alertas

SQS (read-only para métricas del dashboard):
  - sqs:GetQueueUrl, sqs:GetQueueAttributes
  Resource: *
  Razón: El endpoint GET /metrics consulta el tamaño de la DLQ para mostrarlo
         en el dashboard. No puede enviar ni recibir mensajes.

CloudWatch Logs:
  - logs:CreateLogGroup, logs:CreateLogStream, logs:PutLogEvents
  Resource: arn:aws:logs:*:*:*
  Razón: structlog → JSON logs

X-Ray:
  - xray:PutTraceSegments, xray:PutTelemetryRecords
  Resource: *
  Razón: Distributed tracing (aws-xray-sdk)
```

**Qué NO tiene:** Lambda:Invoke, S3, EC2, IAM — ningún permiso de gestión de infraestructura desde el código de la app.

---

### 7.4 GitHub Actions Role — `txn-gateway-github-actions-role`

**Mecanismo de autenticación: OIDC (sin credenciales estáticas)**

En lugar de guardar `AWS_ACCESS_KEY_ID` y `AWS_SECRET_ACCESS_KEY` como secrets de GitHub (que nunca expiran y son difíciles de rotar), el workflow usa **OpenID Connect**:

```
GitHub Actions Runner
  → Solicita JWT token firmado por GitHub (https://token.actions.githubusercontent.com)
  → AWS STS verifica el JWT con el thumbprint del OIDC provider
  → Si el claim "sub" matchea el repo configurado → entrega credenciales temporales (1h)
  → El runner asume el rol y obtiene tokens efímeros
```

**Trust Policy (quién puede asumir el rol):**
```json
{
  "Effect": "Allow",
  "Action": "sts:AssumeRoleWithWebIdentity",
  "Principal": { "Federated": "<OIDC-provider-ARN>" },
  "Condition": {
    "StringEquals": {
      "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
    },
    "StringLike": {
      "token.actions.githubusercontent.com:sub": "repo:BrayanMediina/TXN-Gateway-Monitor-AWS:*"
    }
  }
}
```

El wildcard `:*` permite que cualquier rama/tag/PR del repositorio asuma el rol. En producción se restringiría a `:ref:refs/heads/main` para solo la rama principal.

**Permisos otorgados al rol:**

```
ECR (push de imagen Docker):
  - GetAuthorizationToken, BatchCheckLayerAvailability, GetDownloadUrlForLayer
  - BatchGetImage, PutImage, InitiateLayerUpload, UploadLayerPart, CompleteLayerUpload
  Resource: *
  Razón: GetAuthorizationToken opera a nivel de cuenta, no de repositorio

ECS (despliegue del servicio):
  - UpdateService, DescribeServices, ListTasks, DescribeTasks
  Resource: *
  Razón: ListTasks/DescribeTasks necesitan * (no aceptan ARN de tarea específica
         ya que el ARN no se conoce antes de la ejecución)

EC2 (obtener IP pública del task):
  - DescribeNetworkInterfaces
  Resource: *
  Razón: Para encontrar la ENI del task y extraer su IP pública

Lambda (actualizar código de las 3 funciones):
  - UpdateFunctionCode
  Resource: arn:...:function:txn-*   (txn-processor, txn-reconcile)
            arn:...:function:dlq-*   (dlq-reprocessor)

S3 (deploy del frontend):
  - PutObject, DeleteObject, ListBucket
  Resource: arn:...:txn-gateway-frontend-709147558620
            arn:...:txn-gateway-frontend-709147558620/*

CloudFront (invalidar caché tras deploy del frontend):
  - CreateInvalidation
  Resource: arn:...:distribution/E262ESWDTB9GPB

API Gateway (actualizar IP del backend en el proxy):
  - apigateway:GET   → get-apis, get-integrations (buscar IDs dinámicamente)
  - apigateway:PATCH → update-integration (actualizar integration_uri con nueva IP)
  Resource GET:   *  (GetApis opera sobre la colección, sin ARN específico)
  Resource PATCH: arn:aws:apigateway:us-east-1::/apis/xkokv2ttg8/integrations/*
```

**Qué NO tiene:** IAM manage permissions, RDS, EC2 create/terminate, CloudFormation. El rol solo puede hacer exactamente lo que el pipeline necesita.

---

### 7.5 OIDC Provider

```
URL:        https://token.actions.githubusercontent.com
Client ID:  sts.amazonaws.com
Thumbprint: 6938fd4d98bab03faadb97b34396831e3780aea1
```

El thumbprint es el SHA-1 del certificado TLS raíz de GitHub Actions. AWS lo usa para verificar que los JWT que recibe son genuinamente de GitHub y no de un atacante que finge ser GitHub.

---

## 8. CI/CD — GitHub Actions

### `ci.yml` — Corre en Pull Request

```
lint-and-test-gateway
  ├── Python 3.12 setup
  ├── pip install -r requirements-dev.txt + pip install -e .
  ├── ruff check (linting)
  ├── mypy (type checking)
  └── coverage run pytest (mínimo 85% cobertura)

lint-and-test-lambdas (matrix: txn_processor, dlq_handler, reconcile)
  ├── pip install boto3 pytest moto coverage ruff
  ├── ruff check
  └── coverage run pytest (mínimo 80% cobertura)

build-docker (needs: lint-and-test-gateway)
  ├── docker build
  └── docker run + curl /health (smoke test, sleep 12s)

lint-frontend
  ├── npm ci
  ├── tsc --noEmit (type check)
  └── npm run build (build de producción)
```

### `deploy.yml` — Corre en push a main

```
test (gate, igual que CI gateway)
  └── Si falla: el deploy no corre

deploy (needs: test)
  ├── configure-aws-credentials (OIDC)
  ├── amazon-ecr-login
  ├── docker build + tag + push (imagen:sha + imagen:latest)
  ├── aws ecs update-service --desired-count 1 --force-new-deployment
  ├── Deploy Lambda functions (zip + update-function-code × 3)
  ├── aws ecs wait services-stable
  ├── Obtener IP del nuevo task ECS
  │     list-tasks → describe-tasks → describe-network-interfaces → PublicIp
  ├── Actualizar API Gateway integration_uri con nueva IP
  │     get-apis (por nombre) → get-integrations → update-integration
  └── Deploy frontend a S3 (si secret FRONTEND_S3_BUCKET configurado)
        npm ci + npm run build (usa .env.production para VITE_API_URL)
        aws s3 sync --delete
        cloudfront create-invalidation
```

---

## 9. Observabilidad

### CloudWatch Dashboard — `TXN-Gateway-Monitor`

7 paneles en 2 filas:
1. **SQS throughput** — mensajes enviados/recibidos en `txn-events-queue`
2. **DLQ count** — `ApproximateNumberOfMessagesVisible` en `txn-dlq`
3. **Lambda Errors** — errores de las 3 funciones
4. **Lambda P95** — duración p95 de txn-processor y dlq-reprocessor
5. **ECS CPU/Mem** — utilización del servicio gateway
6. **Stuck Transactions** — métrica custom `TXNGateway/SLO::StuckTransactions`
7. **Alarmas activas** — widget de estado de la alarma DLQ

### CloudWatch Alarm

- **`txn-dlq-messages-visible`**: Se dispara cuando la DLQ tiene > 5 mensajes en 5 minutos. Acción: publica a `txn-alerts-topic` → email.

### Structured Logging (structlog)

El gateway service usa `structlog` con formato JSON. Cada log incluye:
```json
{
  "event": "publish_request_received",
  "txn_id": "abc-123",
  "amount": 1500.00,
  "level": "info",
  "timestamp": "2026-06-18T10:00:00Z"
}
```
Los logs fluyen: container stdout → CloudWatch Logs `/ecs/gateway-service` vía `awslogs` driver.

---

## 10. Seguridad — hallazgos y estado

| # | Hallazgo | Severidad | Estado | Archivo |
|---|----------|-----------|--------|---------|
| 1 | CORS `allow_origins=["*"]` | Medium | **Corregido** — restringido a CloudFront domain | `main.py:36` |
| 2 | ECS puerto 8000 accesible directamente (bypass API GW) | Medium | **Documentado** — requiere VPC Link para fix completo | `modules/ecs/main.tf:166` |
| 3 | `dlq_handler` usa Key incompleta en DynamoDB (falta timestamp) | High | **Corregido** — clave compuesta incluida | `lambdas/dlq_handler/handler.py:72` |

### Mejoras de producción pendientes

- **VPC Link:** Mover ECS a subnet privada, API Gateway conecta vía VPC Link. Elimina IP pública del task y el security group abierto.
- **Autenticación en endpoints:** POST /events/publish no requiere auth. En producción: API Key en API Gateway o Cognito Authorizer.
- **OIDC sub claim más restrictivo:** El trust policy usa `repo:BrayanMediina/TXN-Gateway-Monitor-AWS:*`. En producción: restringir a `ref:refs/heads/main`.
- **Secrets Manager para SNS ARNs:** Actualmente son variables de entorno en la Task Definition. Para datos más sensibles usar AWS Secrets Manager con rotación.
