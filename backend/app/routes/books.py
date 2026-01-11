from __future__ import annotations

from typing import Any, Dict

from ..http import json_response
from ..keys import pk
from ..parsing import querystring


def get_books(event: Dict[str, Any], *, origin: str, table: Any) -> Dict[str, Any]:
    """
    List known books in the personal library (deduped by ISBN).
    """
    from boto3.dynamodb.conditions import Key  # type: ignore

    qs = querystring(event)
    limit_raw = qs.get("limit")
    try:
        limit = int(limit_raw) if limit_raw else 100
        limit = max(1, min(500, limit))
    except Exception:
        return json_response(400, {"error": "limit must be an integer"}, origin=origin)

    resp = table.query(
        KeyConditionExpression=Key("pk").eq(pk()) & Key("sk").begins_with("BOOK#"),
        ScanIndexForward=True,
        Limit=limit,
    )
    items = resp.get("Items") or []

    books = []
    for it in items:
        books.append(
            {
                "isbn": it.get("isbn"),
                "title": it.get("title"),
                "authors": it.get("authors") or [],
                "publishedDate": it.get("publishedDate"),
                "pageCount": it.get("pageCount"),
                "categories": it.get("categories") or [],
                "thumbnail": it.get("thumbnail"),
                "googleVolumeId": it.get("googleVolumeId"),
                "updatedAt": it.get("updatedAt"),
                "createdAt": it.get("createdAt"),
            }
        )

    return json_response(200, {"books": books}, origin=origin)
