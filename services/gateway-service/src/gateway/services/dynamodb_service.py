import time
from typing import Any

import boto3
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
                KeyConditionExpression=boto3.dynamodb.conditions.Key("txnId").eq(txn_id),
                Limit=1,
            )
            items = response.get("Items", [])
            return items[0] if items else None
        except (BotoCoreError, ClientError) as exc:
            logger.error("dynamodb_get_failed", txn_id=txn_id, error=str(exc))
            raise DynamoDBError(f"Error consultando transacción: {exc}") from exc
