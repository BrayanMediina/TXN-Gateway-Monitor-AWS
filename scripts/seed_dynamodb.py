#!/usr/bin/env python3
"""
Seed inicial de DynamoDB con transacciones de ejemplo.
Uso: python seed_dynamodb.py [--table TABLE] [--region REGION] [--count N]
"""
import argparse
import random
import string
import time
import uuid
from datetime import datetime, timedelta, timezone

import boto3


def random_account() -> str:
    return "".join(random.choices(string.digits + string.ascii_uppercase, k=12))


def make_item(minutes_ago: int = 0) -> dict:
    ts = (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)).isoformat()
    status = random.choices(
        ["PROCESSED", "PENDING", "FAILED", "RETRYING"],
        weights=[80, 10, 7, 3],
    )[0]
    amount = round(random.uniform(50, 75_000), 2)
    ttl = int(time.time()) + (7 * 24 * 60 * 60)

    return {
        "txnId": str(uuid.uuid4()),
        "timestamp": ts,
        "amount": str(amount),
        "currency": "USD",
        "txn_type": random.choice(["PAYMENT", "TRANSFER", "WITHDRAWAL", "DEPOSIT"]),
        "source_account": random_account(),
        "destination_account": random_account(),
        "status": status,
        "retry_count": random.randint(0, 3) if status in ("RETRYING", "FAILED") else 0,
        "sqs_message_id": str(uuid.uuid4()),
        "ttl": ttl,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed DynamoDB con datos de ejemplo")
    parser.add_argument("--table", default="txn-events", help="Nombre de la tabla DynamoDB")
    parser.add_argument("--region", default="us-east-1", help="Región AWS")
    parser.add_argument("--count", type=int, default=50, help="Número de items a insertar")
    args = parser.parse_args()

    ddb = boto3.resource("dynamodb", region_name=args.region)
    table = ddb.Table(args.table)

    print(f"Insertando {args.count} items en {args.table} ({args.region})...")

    with table.batch_writer() as batch:
        for i in range(args.count):
            minutes_ago = random.randint(0, 120)
            item = make_item(minutes_ago=minutes_ago)
            batch.put_item(Item=item)
            if (i + 1) % 10 == 0:
                print(f"  {i + 1}/{args.count} insertados")

    print(f"Seed completado: {args.count} items en '{args.table}'")


if __name__ == "__main__":
    main()
