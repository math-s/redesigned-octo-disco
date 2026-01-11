from __future__ import annotations

from typing import Any, Dict

from ..http import json_response
from ..booklib import google_books_lookup, normalize_isbn
from ..keys import book_sk, pk
from ..parsing import parse_json_body
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


def post_book(
    event: Dict[str, Any],
    *,
    origin: str,
    table: Any,
    now_iso: Any,
) -> Dict[str, Any]:
    data, err = parse_json_body(event)
    if err:
        return json_response(400, {"error": err}, origin=origin)

    isbn = normalize_isbn(data.get("isbn"))
    if isbn is None:
        return json_response(400, {"error": "isbn is required (ISBN-10 or ISBN-13)"}, origin=origin)

    try:
        meta = google_books_lookup(isbn)
    except Exception:
        return json_response(502, {"error": "google_books_lookup_failed"}, origin=origin)
    if meta is None:
        return json_response(404, {"error": "book_not_found_for_isbn"}, origin=origin)

    now = now_iso()
    authors = meta.get("authors") or []
    if not isinstance(authors, list):
        authors = []
    authors = [str(a) for a in authors if str(a).strip()]

    expr_parts = [
        "updatedAt = :u",
        "createdAt = if_not_exists(createdAt, :c)",
        "isbn = :isbn",
        "authors = :a",
        "googleFetchedAt = :gf",
        "inLibrary = :il",
    ]
    expr_vals: Dict[str, Any] = {":u": now, ":c": now, ":isbn": isbn, ":a": authors, ":gf": now, ":il": True}

    if meta.get("title") is not None:
        expr_parts.append("title = :t")
        expr_vals[":t"] = str(meta.get("title"))
    if meta.get("publishedDate") is not None:
        expr_parts.append("publishedDate = :pd")
        expr_vals[":pd"] = str(meta.get("publishedDate"))
    if meta.get("pageCount") is not None:
        expr_parts.append("pageCount = :pc")
        expr_vals[":pc"] = meta.get("pageCount")
    if meta.get("categories") is not None:
        expr_parts.append("categories = :cat")
        expr_vals[":cat"] = meta.get("categories") or []
    if meta.get("thumbnail") is not None:
        expr_parts.append("thumbnail = :th")
        expr_vals[":th"] = str(meta.get("thumbnail"))
    if meta.get("googleVolumeId") is not None:
        expr_parts.append("googleVolumeId = :gvid")
        expr_vals[":gvid"] = str(meta.get("googleVolumeId"))
    volume_info = meta.get("googleVolumeInfo")
    if isinstance(volume_info, dict) and volume_info:
        expr_parts.append("googleVolumeInfo = :gvi")
        expr_vals[":gvi"] = volume_info

    table.update_item(
        Key={"pk": pk(), "sk": book_sk(isbn)},
        UpdateExpression="SET " + ", ".join(expr_parts),
        ExpressionAttributeValues=expr_vals,
    )

    return json_response(
        201,
        {
            "book": {
                "isbn": isbn,
                "sk": book_sk(isbn),
                "title": meta.get("title"),
                "authors": authors,
            }
        },
        origin=origin,
    )
