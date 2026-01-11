from __future__ import annotations

import json
from typing import Any, Dict, Optional, Tuple


def parse_json_body(event: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    raw = event.get("body")
    if raw is None:
        return None, "Missing request body"
    try:
        if event.get("isBase64Encoded"):
            import base64

            raw = base64.b64decode(raw).decode("utf-8")
        data = json.loads(raw)
        if not isinstance(data, dict):
            return None, "JSON body must be an object"
        return data, None
    except Exception:
        return None, "Invalid JSON body"


def querystring(event: Dict[str, Any]) -> Dict[str, str]:
    qs = event.get("queryStringParameters") or {}
    return {k: v for k, v in qs.items() if v is not None}


def path(event: Dict[str, Any]) -> str:
    return event.get("rawPath") or event.get("path") or "/"


def method(event: Dict[str, Any]) -> str:
    ctx = event.get("requestContext") or {}
    http = ctx.get("http") or {}
    m = http.get("method") or event.get("httpMethod") or "GET"
    return str(m).upper()


def parse_year(value: Optional[str]) -> Optional[int]:
    if value is None:
        return None
    try:
        y = int(value)
        if y < 1970 or y > 3000:
            return None
        return y
    except Exception:
        return None

