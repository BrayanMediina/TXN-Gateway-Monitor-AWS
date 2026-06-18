from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # AWS
    aws_region: str = "us-east-1"
    aws_account_id: str = ""

    # SNS
    sns_gateway_topic_arn: str = ""
    sns_alerts_topic_arn: str = ""

    # DynamoDB
    dynamodb_txn_table: str = "txn-events"
    dynamodb_metrics_table: str = "gw-metrics"

    # App
    app_env: str = "development"
    log_level: str = "INFO"
    service_name: str = "gateway-service"


@lru_cache
def get_settings() -> Settings:
    return Settings()
