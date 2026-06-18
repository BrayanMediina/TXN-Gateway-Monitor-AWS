import os

import boto3
import pytest
from moto import mock_aws

# Variables de entorno para tests — apuntan a recursos mock
os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
os.environ["AWS_SECURITY_TOKEN"] = "testing"
os.environ["AWS_SESSION_TOKEN"] = "testing"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ["AWS_REGION"] = "us-east-1"
os.environ["SNS_GATEWAY_TOPIC_ARN"] = "arn:aws:sns:us-east-1:123456789012:txn-gateway-topic"
os.environ["SNS_ALERTS_TOPIC_ARN"] = "arn:aws:sns:us-east-1:123456789012:txn-alerts-topic"
os.environ["DYNAMODB_TXN_TABLE"] = "txn-events-test"
os.environ["DYNAMODB_METRICS_TABLE"] = "gw-metrics-test"
os.environ["APP_ENV"] = "test"


@pytest.fixture(scope="function")
def aws_credentials():
    """Credenciales mock para moto."""
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"


@pytest.fixture(scope="function")
def dynamodb_table(aws_credentials):
    """Tabla DynamoDB mock para tests."""
    with mock_aws():
        client = boto3.resource("dynamodb", region_name="us-east-1")
        table = client.create_table(
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
        yield table


@pytest.fixture(scope="function")
def sns_topic(aws_credentials):
    """SNS Topic mock para tests."""
    with mock_aws():
        client = boto3.client("sns", region_name="us-east-1")
        topic = client.create_topic(Name="txn-gateway-topic")
        yield topic["TopicArn"]
