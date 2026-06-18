import os

import boto3
import pytest
from moto import mock_aws

from gateway.models.transaction import TransactionEvent


@pytest.fixture
def table_and_event():
    with mock_aws():
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
                {"AttributeName": "status", "AttributeType": "S"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "status-index",
                    "KeySchema": [
                        {"AttributeName": "status", "KeyType": "HASH"},
                        {"AttributeName": "timestamp", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                }
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        os.environ["DYNAMODB_TXN_TABLE"] = "txn-events-test"

        event = TransactionEvent(
            amount=500.00,
            txn_type="TRANSFER",
            source_account="AAAAAAAAAA11",
            destination_account="BBBBBBBBBB22",
        )
        table.put_item(
            Item={
                "txnId": event.txn_id,
                "timestamp": event.timestamp,
                "amount": str(event.amount),
                "status": "PROCESSED",
                "txn_type": event.txn_type,
            }
        )
        yield table, event


class TestTransactionRepository:
    def test_list_by_status(self, table_and_event) -> None:
        _, event = table_and_event

        from gateway.config import get_settings
        get_settings.cache_clear()

        from gateway.repositories.txn_repository import TransactionRepository

        repo = TransactionRepository()
        items = repo.list_by_status("PROCESSED")
        assert len(items) >= 1
        assert any(i["txnId"] == event.txn_id for i in items)

    def test_list_recent(self, table_and_event) -> None:
        _, event = table_and_event

        from gateway.config import get_settings
        get_settings.cache_clear()

        from gateway.repositories.txn_repository import TransactionRepository

        repo = TransactionRepository()
        items = repo.list_recent()
        assert len(items) >= 1
