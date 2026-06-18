import json

import boto3
import structlog
from botocore.exceptions import BotoCoreError, ClientError

from gateway.config import get_settings
from gateway.exceptions.handlers import SNSPublishError
from gateway.models.transaction import TransactionEvent

logger = structlog.get_logger(__name__)


class SNSService:
    def __init__(self) -> None:
        self._settings = get_settings()
        self._client = boto3.client("sns", region_name=self._settings.aws_region)

    async def publish_transaction(self, event: TransactionEvent) -> str:
        """Publica un evento transaccional en el SNS Topic principal. Retorna el MessageId."""
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
