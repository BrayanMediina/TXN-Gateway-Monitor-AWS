from typing import Any

import boto3
import structlog
from boto3.dynamodb.conditions import Key
from botocore.exceptions import BotoCoreError, ClientError

from gateway.config import get_settings
from gateway.exceptions.handlers import DynamoDBError

logger = structlog.get_logger(__name__)


class TransactionRepository:
    """Acceso directo a DynamoDB para consultas avanzadas."""

    def __init__(self) -> None:
        self._settings = get_settings()
        self._resource = boto3.resource("dynamodb", region_name=self._settings.aws_region)
        self._table = self._resource.Table(self._settings.dynamodb_txn_table)

    def list_by_status(self, status: str, limit: int = 50) -> list[dict[str, Any]]:
        try:
            response = self._table.query(
                IndexName="status-index",
                KeyConditionExpression=Key("status").eq(status),
                Limit=limit,
                ScanIndexForward=False,
            )
            return response.get("Items", [])
        except (BotoCoreError, ClientError) as exc:
            logger.error("list_by_status_failed", status=status, error=str(exc))
            raise DynamoDBError(f"Error listando por estado: {exc}") from exc

    def list_recent(self, limit: int = 50) -> list[dict[str, Any]]:
        try:
            response = self._table.scan(Limit=limit)
            items: list[dict[str, Any]] = response.get("Items", [])
            return sorted(items, key=lambda x: x.get("timestamp", ""), reverse=True)
        except (BotoCoreError, ClientError) as exc:
            logger.error("list_recent_failed", error=str(exc))
            raise DynamoDBError(f"Error listando transacciones: {exc}") from exc
