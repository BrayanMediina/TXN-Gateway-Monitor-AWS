"""
Lambda: dlq-reprocessor
Trigger: SQS DLQ (txn-dlq)
Responsabilidad: Reintentar procesamiento con backoff exponencial.
"""
import json
import logging
import os
import time
from typing import Any

import boto3

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
