#!/usr/bin/env python3
"""
Generador de transacciones de prueba para TXN Gateway Monitor.
Uso: python simulate_events.py [--count N] [--high-value] [--url URL]
"""
import argparse
import json
import random
import string
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone

API_URL = "http://localhost:8000"
TXN_TYPES = ["PAYMENT", "TRANSFER", "WITHDRAWAL", "DEPOSIT"]


def random_account() -> str:
    return "".join(random.choices(string.digits + string.ascii_uppercase, k=12))


def generate_transaction(high_value: bool = False) -> dict:
    amount = (
        round(random.uniform(50_001, 200_000), 2)
        if high_value
        else round(random.uniform(1, 49_999), 2)
    )
    return {
        "amount": amount,
        "currency": "USD",
        "txn_type": random.choice(TXN_TYPES),
        "source_account": random_account(),
        "destination_account": random_account(),
        "metadata": {
            "channel": random.choice(["web", "mobile", "atm", "branch"]),
            "simulated": True,
        },
    }


def publish(payload: dict, base_url: str) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{base_url}/events/publish",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


def main() -> None:
    parser = argparse.ArgumentParser(description="Simulador de transacciones TXN Gateway")
    parser.add_argument("--count", type=int, default=10, help="Número de transacciones a enviar")
    parser.add_argument("--high-value", action="store_true", help="Generar transacciones de alto valor")
    parser.add_argument("--url", default=API_URL, help="URL base del gateway-service")
    parser.add_argument("--delay", type=float, default=0.5, help="Segundos entre transacciones")
    args = parser.parse_args()

    print(f"Enviando {args.count} transacciones a {args.url}")
    print(f"Modo: {'ALTO VALOR' if args.high_value else 'normal'}")
    print("-" * 50)

    success = 0
    errors = 0
    for i in range(1, args.count + 1):
        payload = generate_transaction(high_value=args.high_value)
        try:
            result = publish(payload, args.url)
            print(
                f"[{i:03d}] OK  txn_id={result['txn_id'][:8]} "
                f"amount={payload['amount']:>10,.2f} "
                f"type={payload['txn_type']}"
            )
            success += 1
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8")
            print(f"[{i:03d}] ERR HTTP {exc.code}: {body}")
            errors += 1
        except Exception as exc:
            print(f"[{i:03d}] ERR {exc}")
            errors += 1

        if i < args.count:
            time.sleep(args.delay)

    print("-" * 50)
    print(f"Completado: {success} exitosas, {errors} errores")


if __name__ == "__main__":
    main()
