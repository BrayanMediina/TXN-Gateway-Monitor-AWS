import uuid
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field, field_validator

TransactionType = Literal["PAYMENT", "TRANSFER", "WITHDRAWAL", "DEPOSIT"]
TransactionStatus = Literal["PENDING", "PROCESSED", "FAILED", "RETRYING"]


class TransactionEvent(BaseModel):
    txn_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    amount: float = Field(gt=0, description="Monto en USD, debe ser mayor a 0")
    currency: str = Field(default="USD", min_length=3, max_length=3)
    txn_type: TransactionType
    source_account: str = Field(min_length=10, max_length=20)
    destination_account: str = Field(min_length=10, max_length=20)
    metadata: dict = Field(default_factory=dict)
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v: float) -> float:
        if v > 1_000_000:
            raise ValueError("Monto excede límite máximo de 1,000,000")
        return round(v, 2)


class TransactionResponse(BaseModel):
    txn_id: str
    status: TransactionStatus
    sns_message_id: str
    timestamp: str
    message: str
