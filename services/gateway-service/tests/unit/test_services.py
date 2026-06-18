import asyncio
import os

import boto3
import pytest
from moto import mock_aws

from gateway.exceptions.handlers import SNSPublishError
from gateway.models.transaction import TransactionEvent


@pytest.fixture
def sample_event() -> TransactionEvent:
    return TransactionEvent(
        amount=1500.00,
        txn_type="PAYMENT",
        source_account="1234567890AB",
        destination_account="0987654321CD",
        currency="USD",
    )


class TestSNSService:
    @mock_aws
    def test_publish_transaction_success(self, sample_event: TransactionEvent) -> None:
        sns_client = boto3.client("sns", region_name="us-east-1")
        topic = sns_client.create_topic(Name="txn-gateway-topic")
        topic_arn = topic["TopicArn"]

        os.environ["SNS_GATEWAY_TOPIC_ARN"] = topic_arn

        from gateway.config import get_settings
        get_settings.cache_clear()

        from gateway.services.sns_service import SNSService

        service = SNSService()
        message_id = asyncio.run(service.publish_transaction(sample_event))

        assert message_id is not None
        assert len(message_id) > 0

    @mock_aws
    def test_publish_transaction_raises_on_invalid_arn(self, sample_event: TransactionEvent) -> None:
        os.environ["SNS_GATEWAY_TOPIC_ARN"] = "arn:aws:sns:us-east-1:000000000000:nonexistent"

        from gateway.config import get_settings
        get_settings.cache_clear()

        from gateway.services.sns_service import SNSService

        service = SNSService()
        with pytest.raises(SNSPublishError):
            asyncio.run(service.publish_transaction(sample_event))


class TestDynamoDBService:
    @mock_aws
    def test_save_transaction_success(self, sample_event: TransactionEvent) -> None:
        ddb = boto3.resource("dynamodb", region_name="us-east-1")
        table = ddb.create_table(
            TableName="txn-events-test",
            KeySchema=[
                {"AttributeName": "txnId", "KeyType": "HASH"},
                {"AttributeName": "timestamp", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "txnId", "AttributeType": "S"},
                {"AttributeName": "timestamp", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        os.environ["DYNAMODB_TXN_TABLE"] = "txn-events-test"

        from gateway.config import get_settings
        get_settings.cache_clear()

        from gateway.services.dynamodb_service import DynamoDBService

        service = DynamoDBService()
        asyncio.run(service.save_transaction(sample_event, status="PENDING"))

        response = table.get_item(
            Key={"txnId": sample_event.txn_id, "timestamp": sample_event.timestamp}
        )
        assert "Item" in response
        assert response["Item"]["status"] == "PENDING"

    @mock_aws
    def test_save_transaction_idempotent(self, sample_event: TransactionEvent) -> None:
        ddb = boto3.resource("dynamodb", region_name="us-east-1")
        ddb.create_table(
            TableName="txn-events-test",
            KeySchema=[
                {"AttributeName": "txnId", "KeyType": "HASH"},
                {"AttributeName": "timestamp", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "txnId", "AttributeType": "S"},
                {"AttributeName": "timestamp", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        os.environ["DYNAMODB_TXN_TABLE"] = "txn-events-test"

        from gateway.config import get_settings
        get_settings.cache_clear()

        from gateway.services.dynamodb_service import DynamoDBService

        service = DynamoDBService()
        # Segunda llamada no debe lanzar excepción (idempotencia)
        asyncio.run(service.save_transaction(sample_event, status="PENDING"))
        asyncio.run(service.save_transaction(sample_event, status="PENDING"))
