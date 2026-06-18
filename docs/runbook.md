# Runbook — TXN Gateway Monitor

**Última actualización:** 2024-01-01  
**Responsable on-call:** Equipo de Operaciones

---

## Alertas y Respuesta a Incidentes

### ALERTA: DLQ con > 5 mensajes visibles

**Síntoma:** CloudWatch Alarm `txn-dlq-messages-visible` en estado ALARM.  
**Severidad:** P2

**Pasos de investigación:**
1. Verificar logs de `txn-processor` Lambda en CloudWatch:
   ```
   /aws/lambda/txn-processor
   ```
2. Revisar errores comunes:
   - `ConditionalCheckFailedException`: duplicado — generalmente inofensivo
   - `ProvisionedThroughputExceededException`: DynamoDB bajo carga, aumentar capacidad
   - `ClientError: AccessDenied`: revisar IAM roles
3. Verificar estado de DynamoDB:
   ```bash
   aws dynamodb describe-table --table-name txn-events --query 'Table.TableStatus'
   ```

**Resolución:**
- Si los mensajes en DLQ son < 50 y el error es transitorio, el `dlq-reprocessor` los reintentará automáticamente
- Si > 50 mensajes y error persistente: escalar a P1 e investigar la causa raíz antes de reencolar manualmente

---

### ALERTA: Transacciones PENDING stuck (> 10 minutos)

**Síntoma:** SNS Alert con subject `[RECONCILE] N transacciones PENDING stuck`.  
**Severidad:** P2

**Pasos de investigación:**
1. Verificar que la Lambda `txn-processor` esté recibiendo mensajes SQS:
   ```bash
   aws sqs get-queue-attributes \
     --queue-url <URL> \
     --attribute-names ApproximateNumberOfMessages ApproximateNumberOfMessagesNotVisible
   ```
2. Verificar estado de la cola:
   ```bash
   aws sqs get-queue-attributes --queue-url <URL> --attribute-names All
   ```
3. Ver logs del reconciliador:
   ```
   /aws/lambda/txn-reconcile
   ```

**Resolución:**
- Verificar que el event source mapping de SQS → Lambda esté habilitado:
  ```bash
  aws lambda list-event-source-mappings --function-name txn-processor
  ```
- Si está deshabilitado, habilitarlo:
  ```bash
  aws lambda update-event-source-mapping --uuid <UUID> --enabled
  ```

---

### ALERTA: Transacción alto valor detectada

**Síntoma:** SNS Alert con subject `[ALERTA] Transacción alto valor`.  
**Severidad:** P3 (informativa, no requiere acción inmediata)

**Pasos:**
1. Confirmar que la transacción es legítima en el sistema de origen
2. Si es sospechosa, escalar al equipo de fraude
3. No se requiere acción técnica; el sistema procesó la transacción correctamente

---

### INCIDENTE: gateway-service no responde (ECS)

**Síntoma:** `/health` HTTP no devuelve 200.  
**Severidad:** P1

**Pasos de investigación:**
1. Verificar estado del servicio ECS:
   ```bash
   aws ecs describe-services --cluster txn-gateway-cluster --services gateway-service
   ```
2. Ver logs del contenedor:
   ```bash
   aws logs tail /ecs/gateway-service --follow
   ```
3. Verificar tareas en ejecución:
   ```bash
   aws ecs list-tasks --cluster txn-gateway-cluster --service-name gateway-service
   ```

**Resolución:**
- Forzar nuevo despliegue (rolling update):
  ```bash
  aws ecs update-service \
    --cluster txn-gateway-cluster \
    --service gateway-service \
    --force-new-deployment
  ```
- Esperar estabilización:
  ```bash
  aws ecs wait services-stable \
    --cluster txn-gateway-cluster \
    --services gateway-service
  ```

---

## Operaciones rutinarias

### Verificar salud del sistema

```bash
./scripts/check_health.sh http://<ALB-URL>
```

### Enviar transacciones de prueba

```bash
# 10 transacciones normales
python scripts/simulate_events.py --count 10 --url http://<ALB-URL>

# 5 transacciones de alto valor (dispara alerta)
python scripts/simulate_events.py --count 5 --high-value --url http://<ALB-URL>
```

### Consultar métricas de SLO

```bash
aws cloudwatch get-metric-statistics \
  --namespace TXNGateway/SLO \
  --metric-name StuckTransactions \
  --dimensions Name=Environment,Value=dev \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Sum
```

### Limpiar mensajes de DLQ manualmente (emergencia)

```bash
aws sqs purge-queue --queue-url $(aws sqs get-queue-url --queue-name txn-dlq --query QueueUrl --output text)
```

> **ADVERTENCIA:** `purge-queue` elimina todos los mensajes permanentemente. Solo usar como último recurso.

---

## Contactos de escalada

| Nivel | Responsable | Canal |
|---|---|---|
| P1 (crítico) | On-call Engineer | PagerDuty + Slack #incidents |
| P2 (alto) | Equipo Ops | Slack #alerts |
| P3 (informativo) | Equipo Ops | Email |

---

## SLOs de referencia

| Indicador | Objetivo | Alarma |
|---|---|---|
| Disponibilidad gateway | 99.5% | < 99% |
| Tasa procesamiento exitoso | 99.0% | < 97% |
| Latencia P95 | < 2 seg | > 3 seg |
| Mensajes DLQ acumulados | < 5 | > 5 |
| Tiempo detección alerta fraude | < 30 seg | > 60 seg |
