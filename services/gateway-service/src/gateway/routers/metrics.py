from typing import Any

import boto3
import structlog
from fastapi import APIRouter

from gateway.config import get_settings
from gateway.services.dynamodb_service import DynamoDBService

router = APIRouter(prefix="/metrics", tags=["metrics"])
logger = structlog.get_logger(__name__)


def get_db_service() -> DynamoDBService:
    return DynamoDBService()


def _get_dlq_count() -> int:
    try:
        settings = get_settings()
        sqs = boto3.client("sqs", region_name=settings.aws_region)
        url_resp = sqs.get_queue_url(QueueName="txn-dlq")
        attrs = sqs.get_queue_attributes(
            QueueUrl=url_resp["QueueUrl"],
            AttributeNames=["ApproximateNumberOfMessages"],
        )
        return int(attrs["Attributes"].get("ApproximateNumberOfMessages", 0))
    except Exception as exc:
        logger.warning("dlq_count_unavailable", error=str(exc))
        return 0


@router.get(
    "",
    summary="Métricas del dashboard",
    description="Retorna KPIs calculados desde DynamoDB y SQS para el dashboard en tiempo real.",
)
async def get_metrics() -> dict[str, Any]:
    db = get_db_service()
    data = await db.get_metrics_data()
    dlq_count = _get_dlq_count()

    logger.info(
        "metrics_requested",
        txn_per_hour=data["txn_per_hour"],
        success_rate=data["success_rate"],
        dlq_count=dlq_count,
    )

    return {
        "txnPerHour": data["txn_per_hour"],
        "successRate": data["success_rate"],
        "dlqCount": dlq_count,
        "p95Latency": 0,
        "timeline": data["timeline"],
    }
