"""
Lambda: txn-processor
Trigger: SQS Queue (txn-events-queue)
Responsabilidad: Consumir mensajes SQS, validar y persistir en DynamoDB.
"""
import json
import logging
import os
import time
from typing import Any

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

dynamodb = boto3.resource("dynamodb", region_name=os.environ["AWS_REGION"])
table = dynamodb.Table(os.environ["DYNAMODB_TABLE"])
sns_client = boto3.client("sns", region_name=os.environ["AWS_REGION"])

ALERTS_TOPIC_ARN = os.environ["SNS_ALERTS_TOPIC_ARN"]
HIGH_VALUE_THRESHOLD = float(os.environ.get("HIGH_VALUE_THRESHOLD", "50000"))


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Procesa batch de mensajes SQS con partial batch failure support."""
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
