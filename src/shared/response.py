"""Standard API Gateway response helpers with CORS and Decimal support."""

from __future__ import annotations

import json
import os
from decimal import Decimal


class _DecimalEncoder(json.JSONEncoder):
    """Serialise ``Decimal`` (returned by DynamoDB) to ``float``."""

    def default(self, obj):
        if isinstance(obj, Decimal):
            if obj == int(obj):
                return int(obj)
            return float(obj)
        return super().default(obj)


def _cors_headers() -> dict[str, str]:
    origin = os.environ.get("FRONTEND_ORIGIN", "*")
    return {
        "Access-Control-Allow-Origin": origin,
        "Access-Control-Allow-Headers": "Content-Type",
        "Access-Control-Allow-Methods": "GET,POST,PATCH,OPTIONS",
    }


def success(body: dict, status_code: int = 200) -> dict:
    return {
        "statusCode": status_code,
        "headers": {**_cors_headers(), "Content-Type": "application/json"},
        "body": json.dumps(body, cls=_DecimalEncoder, default=str),
    }


def error(message: str, status_code: int = 400) -> dict:
    return {
        "statusCode": status_code,
        "headers": {**_cors_headers(), "Content-Type": "application/json"},
        "body": json.dumps({"error": message}),
    }
