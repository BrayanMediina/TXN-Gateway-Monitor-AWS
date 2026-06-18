from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, Depends, HTTPException, status

from gateway.models.transaction import TransactionEvent, TransactionResponse
from gateway.services.dynamodb_service import DynamoDBService
from gateway.services.sns_service import SNSService

router = APIRouter(prefix="/events", tags=["events"])
logger = structlog.get_logger(__name__)


def get_sns_service() -> SNSService:
    return SNSService()


def get_db_service() -> DynamoDBService:
    return DynamoDBService()


@router.post(
    "/publish",
    response_model=TransactionResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Publicar evento transaccional",
    description="Recibe un evento de transacción, lo valida y lo publica en SNS para procesamiento asíncrono.",
)
async def publish_event(
    event: TransactionEvent,
    sns: SNSService = Depends(get_sns_service),
    db: DynamoDBService = Depends(get_db_service),
) -> TransactionResponse:
    logger.info("publish_request_received", txn_id=event.txn_id, amount=event.amount)

    await db.save_transaction(event, status="PENDING")
    message_id = await sns.publish_transaction(event)
    await db.update_status(event.txn_id, event.timestamp, "PROCESSED", sns_message_id=message_id)

    return TransactionResponse(
        txn_id=event.txn_id,
        status="PROCESSED",
        sns_message_id=message_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
        message="Evento publicado correctamente en el gateway de mensajería",
    )


@router.get(
    "/{txn_id}",
    summary="Consultar estado de transacción",
)
async def get_transaction(
    txn_id: str,
    db: DynamoDBService = Depends(get_db_service),
) -> dict:
    txn = await db.get_transaction(txn_id)
    if not txn:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transacción {txn_id} no encontrada",
        )
    return txn
