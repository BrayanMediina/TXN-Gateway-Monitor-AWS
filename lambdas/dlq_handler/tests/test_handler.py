import json
import os
from unittest.mock import patch

import boto3
import pytest
from moto import mock_aws

os.environ["AWS_REGION"] = "us-east-1"
os.environ["DYNAMODB_TABLE"] = "txn-events-test"
os.environ["MAIN_QUEUE_URL"] = "https://sqs.us-east-1.amazonaws.com/123456789012/txn-events-queue"
os.environ["MAX_RETRIES"] = "3"
os.environ["LOG_LEVEL"] = "INFO"
os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"


def make_dlq_record(txn_id: str, receive_count: int = 1, message_id: str = "dlq-msg-001") -> dict:
    body = {
        "detail": {
            "txn_id": txn_id,
            "amount": 500.0,
            "currency": "USD",
        }
    }
    return {
        "messageId": message_id,
        "body": json.dumps(body),
        "attributes": {"ApproximateReceiveCount": str(receive_count)},
    }


@mock_aws
def test_handler_requeues_within_retry_limit() -> None:
    sqs = boto3.client("sqs", region_name="us-east-1")
    queue = sqs.create_queue(QueueName="txn-events-queue")
    queue_url = queue["QueueUrl"]

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

    os.environ["MAIN_QUEUE_URL"] = queue_url

    import importlib
    import lambdas.dlq_handler.handler as h
    importlib.reload(h)

    event = {"Records": [make_dlq_record("txn-retry", receive_count=1)]}
    result = h.handler(event, None)
    assert result == {"batchItemFailures": []}


@mock_aws
def test_handler_marks_failed_on_max_retries() -> None:
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
    # Pre-seed item
    table.put_item(Item={"txnId": "txn-exhausted", "timestamp": "2024-01-01T00:00:00", "status": "RETRYING"})

    import importlib
    import lambdas.dlq_handler.handler as h
    importlib.reload(h)

    event = {"Records": [make_dlq_record("txn-exhausted", receive_count=4)]}
    result = h.handler(event, None)
    assert result == {"batchItemFailures": []}
