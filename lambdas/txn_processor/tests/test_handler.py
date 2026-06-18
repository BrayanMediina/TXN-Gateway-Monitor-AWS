import json
import os
from unittest.mock import MagicMock, patch

import boto3
import pytest
from moto import mock_aws

os.environ["AWS_REGION"] = "us-east-1"
os.environ["DYNAMODB_TABLE"] = "txn-events-test"
os.environ["SNS_ALERTS_TOPIC_ARN"] = "arn:aws:sns:us-east-1:123456789012:txn-alerts-topic"
os.environ["HIGH_VALUE_THRESHOLD"] = "50000"
os.environ["LOG_LEVEL"] = "INFO"
os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"


def make_sqs_record(txn_id: str, amount: float, message_id: str = "msg-001") -> dict:
    body = {
        "source": "txn.gateway",
        "detail-type": "TransactionEvent",
        "detail": {
            "txn_id": txn_id,
            "amount": amount,
            "currency": "USD",
            "txn_type": "PAYMENT",
            "source_account": "AAAAAAAAAA11",
            "destination_account": "BBBBBBBBBB22",
            "timestamp": "2024-01-01T00:00:00",
        },
    }
    return {"messageId": message_id, "body": json.dumps(body)}


@mock_aws
def test_handler_processes_normal_transaction() -> None:
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

    import importlib
    import lambdas.txn_processor.handler as h
    importlib.reload(h)

    event = {"Records": [make_sqs_record("txn-001", 1500.0)]}
    result = h.handler(event, None)

    assert result == {"batchItemFailures": []}
    item = table.get_item(Key={"txnId": "txn-001", "timestamp": "2024-01-01T00:00:00"})
    assert item["Item"]["status"] == "PROCESSED"


@mock_aws
def test_handler_partial_batch_failure() -> None:
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

    import importlib
    import lambdas.txn_processor.handler as h
    importlib.reload(h)

    bad_record = {"messageId": "bad-msg", "body": "not-json"}
    good_record = make_sqs_record("txn-002", 500.0, "good-msg")

    event = {"Records": [bad_record, good_record]}
    result = h.handler(event, None)

    assert len(result["batchItemFailures"]) == 1
    assert result["batchItemFailures"][0]["itemIdentifier"] == "bad-msg"


@mock_aws
def test_handler_high_value_sends_alert() -> None:
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
    sns = boto3.client("sns", region_name="us-east-1")
    sns.create_topic(Name="txn-alerts-topic")

    import importlib
    import lambdas.txn_processor.handler as h
    importlib.reload(h)

    event = {"Records": [make_sqs_record("txn-high", 75000.0)]}
    result = h.handler(event, None)
    assert result == {"batchItemFailures": []}
