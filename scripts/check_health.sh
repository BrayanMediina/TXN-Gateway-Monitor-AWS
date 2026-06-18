#!/usr/bin/env bash
# Verifica el estado del gateway-service y sus dependencias AWS.
# Uso: ./check_health.sh [URL]

set -euo pipefail

BASE_URL="${1:-http://localhost:8000}"
REGION="${AWS_REGION:-us-east-1}"

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

ok()   { echo -e "${GREEN}[OK]${NC}    $1"; }
fail() { echo -e "${RED}[FAIL]${NC}  $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC}  $1"; }

echo "================================================"
echo " TXN Gateway Monitor — Health Check"
echo " $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
echo "================================================"

# 1. Gateway HTTP health
echo ""
echo "--- gateway-service ---"
HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "${BASE_URL}/health" 2>/dev/null || echo "000")
if [ "$HTTP_STATUS" = "200" ]; then
    BODY=$(curl -s "${BASE_URL}/health")
    ok "HTTP /health → $HTTP_STATUS | $BODY"
else
    fail "HTTP /health → $HTTP_STATUS (servicio no disponible)"
fi

# 2. SQS Queue
echo ""
echo "--- SQS ---"
QUEUE_URL=$(aws sqs get-queue-url --queue-name txn-events-queue --region "$REGION" --query QueueUrl --output text 2>/dev/null || echo "")
if [ -n "$QUEUE_URL" ]; then
    VISIBLE=$(aws sqs get-queue-attributes \
        --queue-url "$QUEUE_URL" \
        --attribute-names ApproximateNumberOfMessages \
        --region "$REGION" \
        --query 'Attributes.ApproximateNumberOfMessages' \
        --output text 2>/dev/null || echo "?")
    ok "txn-events-queue: $VISIBLE mensajes visibles"
else
    fail "txn-events-queue no encontrada"
fi

DLQ_URL=$(aws sqs get-queue-url --queue-name txn-dlq --region "$REGION" --query QueueUrl --output text 2>/dev/null || echo "")
if [ -n "$DLQ_URL" ]; then
    DLQ_VISIBLE=$(aws sqs get-queue-attributes \
        --queue-url "$DLQ_URL" \
        --attribute-names ApproximateNumberOfMessages \
        --region "$REGION" \
        --query 'Attributes.ApproximateNumberOfMessages' \
        --output text 2>/dev/null || echo "?")
    if [ "$DLQ_VISIBLE" -gt 5 ] 2>/dev/null; then
        warn "txn-dlq: $DLQ_VISIBLE mensajes (por encima del SLO de 5)"
    else
        ok "txn-dlq: $DLQ_VISIBLE mensajes"
    fi
else
    fail "txn-dlq no encontrada"
fi

# 3. DynamoDB
echo ""
echo "--- DynamoDB ---"
TABLE_STATUS=$(aws dynamodb describe-table \
    --table-name txn-events \
    --region "$REGION" \
    --query 'Table.TableStatus' \
    --output text 2>/dev/null || echo "NOT_FOUND")
if [ "$TABLE_STATUS" = "ACTIVE" ]; then
    ok "txn-events: $TABLE_STATUS"
else
    fail "txn-events: $TABLE_STATUS"
fi

# 4. Lambda functions
echo ""
echo "--- Lambda ---"
for fn in txn-processor dlq-reprocessor txn-reconcile; do
    STATE=$(aws lambda get-function \
        --function-name "$fn" \
        --region "$REGION" \
        --query 'Configuration.State' \
        --output text 2>/dev/null || echo "NOT_FOUND")
    if [ "$STATE" = "Active" ]; then
        ok "$fn: $STATE"
    else
        fail "$fn: $STATE"
    fi
done

echo ""
echo "================================================"
echo " Health check completado"
echo "================================================"
