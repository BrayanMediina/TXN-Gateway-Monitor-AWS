import os
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient, ASGITransport

os.environ["SNS_GATEWAY_TOPIC_ARN"] = "arn:aws:sns:us-east-1:123456789012:txn-gateway-topic"
os.environ["SNS_ALERTS_TOPIC_ARN"] = "arn:aws:sns:us-east-1:123456789012:txn-alerts-topic"
os.environ["DYNAMODB_TXN_TABLE"] = "txn-events-test"
os.environ["APP_ENV"] = "test"


@pytest.fixture
def app():
    from gateway.config import get_settings
    get_settings.cache_clear()
    from gateway.main import app
    return app


@pytest.mark.asyncio
async def test_health_check(app) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "gateway-service"


@pytest.mark.asyncio
async def test_publish_event_success(app) -> None:
    with patch(
        "gateway.services.sns_service.SNSService.publish_transaction",
        new_callable=AsyncMock,
        return_value="mock-message-id-123",
    ), patch(
        "gateway.services.dynamodb_service.DynamoDBService.save_transaction",
        new_callable=AsyncMock,
    ), patch(
        "gateway.services.dynamodb_service.DynamoDBService.update_status",
        new_callable=AsyncMock,
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/events/publish",
                json={
                    "amount": 1500.00,
                    "txn_type": "PAYMENT",
                    "source_account": "1234567890AB",
                    "destination_account": "0987654321CD",
                    "currency": "USD",
                },
            )
    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "PROCESSED"
    assert data["sns_message_id"] == "mock-message-id-123"


@pytest.mark.asyncio
async def test_publish_event_invalid_amount(app) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/events/publish",
            json={
                "amount": -100,
                "txn_type": "PAYMENT",
                "source_account": "1234567890AB",
                "destination_account": "0987654321CD",
            },
        )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_transaction_not_found(app) -> None:
    with patch(
        "gateway.services.dynamodb_service.DynamoDBService.get_transaction",
        new_callable=AsyncMock,
        return_value=None,
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/events/nonexistent-txn-id")
    assert response.status_code == 404
