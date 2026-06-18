import os
from datetime import datetime, timedelta, timezone

import boto3
import pytest
from moto import mock_aws

os.environ["AWS_REGION"] = "us-east-1"
os.environ["DYNAMODB_TABLE"] = "txn-events-test"
os.environ["SNS_ALERTS_TOPIC_ARN"] = "arn:aws:sns:us-east-1:123456789012:txn-alerts-topic"
os.environ["PENDING_THRESHOLD_MINUTES"] = "10"
os.environ["APP_ENV"] = "test"
os.environ["LOG_LEVEL"] = "INFO"
os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"


def setup_table(ddb):
    return ddb.create_table(
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


@mock_aws
def test_handler_no_stuck_transactions() -> None:
    ddb = boto3.resource("dynamodb", region_name="us-east-1")
    setup_table(ddb)

    import importlib
    import lambdas.reconcile.handler as h
    importlib.reload(h)

    result = h.handler({}, None)
    assert result["status"] == "OK"
    assert result["stuck_transactions"] == 0


@mock_aws
def test_handler_detects_stuck_transactions() -> None:
    ddb = boto3.resource("dynamodb", region_name="us-east-1")
    table = setup_table(ddb)

    # Insertar transacción PENDING antigua (20 minutos atrás)
    old_ts = (datetime.now(timezone.utc) - timedelta(minutes=20)).isoformat()
    table.put_item(
        Item={
            "txnId": "txn-stuck-001",
            "timestamp": old_ts,
            "status": "PENDING",
            "amount": "500",
        }
    )

    boto3.client("sns", region_name="us-east-1").create_topic(Name="txn-alerts-topic")

    import importlib
    import lambdas.reconcile.handler as h
    importlib.reload(h)

    result = h.handler({}, None)
    assert result["status"] == "OK"
    assert result["stuck_transactions"] == 1
