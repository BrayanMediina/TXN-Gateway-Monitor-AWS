import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

import boto3
import boto3.dynamodb.conditions as cond
import structlog
from botocore.exceptions import BotoCoreError, ClientError

from gateway.config import get_settings
from gateway.exceptions.handlers import DynamoDBError
from gateway.models.transaction import TransactionEvent, TransactionStatus

logger = structlog.get_logger(__name__)

TTL_SECONDS = 7 * 24 * 60 * 60  # 7 días


class DynamoDBService:
    def __init__(self) -> None:
        self._settings = get_settings()
        self._resource = boto3.resource("dynamodb", region_name=self._settings.aws_region)
        self._table = self._resource.Table(self._settings.dynamodb_txn_table)

    async def save_transaction(
        self,
        event: TransactionEvent,
        status: TransactionStatus = "PENDING",
    ) -> None:
        ttl = int(time.time()) + TTL_SECONDS
        try:
            self._table.put_item(
                Item={
                    "txnId": event.txn_id,
                    "timestamp": event.timestamp,
                    "amount": str(event.amount),
                    "currency": event.currency,
                    "txn_type": event.txn_type,
                    "source_account": event.source_account,
                    "destination_account": event.destination_account,
                    "metadata": event.metadata,
                    "status": status,
                    "retry_count": 0,
                    "ttl": ttl,
                },
                ConditionExpression="attribute_not_exists(txnId)",
            )
            logger.info("transaction_saved", txn_id=event.txn_id, status=status)
        except ClientError as exc:
            if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
                logger.warning("transaction_already_exists", txn_id=event.txn_id)
                return
            logger.error("dynamodb_save_failed", txn_id=event.txn_id, error=str(exc))
            raise DynamoDBError(f"Error guardando transacción: {exc}") from exc
        except (BotoCoreError, Exception) as exc:
            raise DynamoDBError(f"Error guardando transacción: {exc}") from exc

    async def update_status(
        self,
        txn_id: str,
        timestamp: str,
        status: TransactionStatus,
        sns_message_id: str = "",
    ) -> None:
        try:
            update_expr = "SET #s = :status, updated_at = :ua"
            expr_values: dict[str, Any] = {
                ":status": status,
                ":ua": str(int(time.time())),
            }
            if sns_message_id:
                update_expr += ", sns_message_id = :mid"
                expr_values[":mid"] = sns_message_id

            self._table.update_item(
                Key={"txnId": txn_id, "timestamp": timestamp},
                UpdateExpression=update_expr,
                ExpressionAttributeNames={"#s": "status"},
                ExpressionAttributeValues=expr_values,
            )
            logger.info("transaction_status_updated", txn_id=txn_id, status=status)
        except (BotoCoreError, ClientError) as exc:
            logger.error("dynamodb_update_failed", txn_id=txn_id, error=str(exc))
            raise DynamoDBError(f"Error actualizando estado: {exc}") from exc

    async def get_transaction(self, txn_id: str) -> dict[str, Any] | None:
        try:
            response = self._table.query(
                KeyConditionExpression=cond.Key("txnId").eq(txn_id),
                Limit=1,
            )
            items = response.get("Items", [])
            return items[0] if items else None
        except (BotoCoreError, ClientError) as exc:
            logger.error("dynamodb_get_failed", txn_id=txn_id, error=str(exc))
            raise DynamoDBError(f"Error consultando transacción: {exc}") from exc

    async def list_transactions(self, limit: int = 50) -> list[dict[str, Any]]:
        try:
            response = self._table.scan(Limit=max(limit, 100))
            items: list[dict[str, Any]] = response.get("Items", [])
            items.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
            return items[:limit]
        except (BotoCoreError, ClientError) as exc:
            logger.error("dynamodb_list_failed", error=str(exc))
            raise DynamoDBError(f"Error listando transacciones: {exc}") from exc

    async def get_metrics_data(self) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        one_hour_ago = (now - timedelta(hours=1)).isoformat()
        two_hours_ago = (now - timedelta(hours=2)).isoformat()

        # Contar por status en la última hora usando el GSI status-index
        status_counts: dict[str, int] = {}
        for s in ("PROCESSED", "PENDING", "FAILED", "RETRYING"):
            try:
                resp = self._table.query(
                    IndexName="status-index",
                    KeyConditionExpression=(
                        cond.Key("status").eq(s)
                        & cond.Key("timestamp").gte(one_hour_ago)
                    ),
                    Select="COUNT",
                )
                status_counts[s] = resp.get("Count", 0)
            except (BotoCoreError, ClientError):
                status_counts[s] = 0

        total = sum(status_counts.values())
        processed = status_counts.get("PROCESSED", 0)
        failed = status_counts.get("FAILED", 0)
        success_rate = round((processed / total * 100) if total > 0 else 100.0, 1)

        # Timeline: últimas 2 horas en buckets de 15 minutos
        BUCKET_MINUTES = 15
        NUM_BUCKETS = 8
        buckets: dict[str, dict[str, Any]] = {}
        for i in range(NUM_BUCKETS):
            label = (now - timedelta(minutes=BUCKET_MINUTES * (NUM_BUCKETS - 1 - i))).strftime("%H:%M")
            buckets[label] = {"time": label, "processed": 0, "failed": 0}

        try:
            scan_resp = self._table.scan(
                FilterExpression=cond.Attr("timestamp").gte(two_hours_ago),
                ProjectionExpression="#ts, #st",
                ExpressionAttributeNames={"#ts": "timestamp", "#st": "status"},
            )
            for item in scan_resp.get("Items", []):
                try:
                    ts_str = item.get("timestamp", "")
                    dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                    mins_ago = (now - dt).total_seconds() / 60
                    if mins_ago < 0 or mins_ago >= NUM_BUCKETS * BUCKET_MINUTES:
                        continue
                    bucket_idx = NUM_BUCKETS - 1 - int(mins_ago / BUCKET_MINUTES)
                    label = (now - timedelta(minutes=BUCKET_MINUTES * (NUM_BUCKETS - 1 - bucket_idx))).strftime("%H:%M")
                    if label in buckets:
                        st = item.get("status", "")
                        if st == "PROCESSED":
                            buckets[label]["processed"] += 1
                        elif st in ("FAILED", "RETRYING"):
                            buckets[label]["failed"] += 1
                except (ValueError, TypeError):
                    pass
        except (BotoCoreError, ClientError) as exc:
            logger.warning("timeline_scan_failed", error=str(exc))

        return {
            "txn_per_hour": total,
            "success_rate": success_rate,
            "failed_count": failed,
            "timeline": list(buckets.values()),
        }
