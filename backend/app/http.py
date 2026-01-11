from __future__ import annotations

import json
import os
from decimal import Decimal
from typing import Any, Dict


def origin_from_event(event: Dict[str, Any]) -> str:
    allowed = os.environ.get("ALLOWED_ORIGIN", "*").strip() or "*"
    if allowed == "*":
        return "*"
    headers = event.get("headers") or {}
    req_origin = headers.get("origin") or headers.get("Origin")
    # Keep previous behavior: always return the configured allowed origin.
    return allowed if req_origin == allowed else allowed


def _json_default(obj: Any) -> Any:
    # DynamoDB returns numbers as Decimal.
    if isinstance(obj, Decimal):
        if obj % 1 == 0:
            return int(obj)
        return float(obj)
    raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")


def json_response(status_code: int, body: Dict[str, Any], *, origin: str) -> Dict[str, Any]:
    return {
        "statusCode": status_code,
        "headers": {
            "content-type": "application/json; charset=utf-8",
            "access-control-allow-origin": origin,
            "access-control-allow-headers": "content-type,x-admin-token",
            "access-control-allow-methods": "GET,POST,PATCH,DELETE,OPTIONS",
            "cache-control": "no-store",
        },
        "body": json.dumps(body, separators=(",", ":"), ensure_ascii=False, default=_json_default),
    }


def options_response(*, origin: str) -> Dict[str, Any]:
    return {
        "statusCode": 204,
        "headers": {
            "access-control-allow-origin": origin,
            "access-control-allow-headers": "content-type,x-admin-token",
            "access-control-allow-methods": "GET,POST,PATCH,DELETE,OPTIONS",
            "cache-control": "no-store",
        },
        "body": "",
    }

