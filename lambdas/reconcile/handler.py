"""
Lambda: txn-reconcile
Trigger: EventBridge (rate: 5 minutes)
Responsabilidad: Detectar transacciones PENDING stuck y generar métricas de SLO.
"""
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key

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

    logger.info(
        "Reconciliation run",
        extra={"stuck_count": len(stuck_txns), "run_time": now.isoformat()},
    )

    cloudwatch.put_metric_data(
        Namespace="TXNGateway/SLO",
        MetricData=[
            {
                "MetricName": "StuckTransactions",
                "Value": len(stuck_txns),
                "Unit": "Count",
                "Dimensions": [
                    {"Name": "Environment", "Value": os.environ.get("APP_ENV", "dev")}
                ],
            }
        ],
    )

    if stuck_txns:
        txn_ids = [t.get("txnId") for t in stuck_txns[:10]]  # Primeras 10
        sns_client.publish(
            TopicArn=ALERTS_TOPIC_ARN,
            Subject=f"[RECONCILE] {len(stuck_txns)} transacciones PENDING stuck",
            Message=(
                f"Se detectaron {len(stuck_txns)} transacciones en estado PENDING "
                f"por más de {PENDING_THRESHOLD_MINUTES} minutos.\n"
                f"Primeras TXN IDs: {txn_ids}"
            ),
        )

    return {
        "reconciled_at": now.isoformat(),
        "stuck_transactions": len(stuck_txns),
        "status": "OK",
    }
