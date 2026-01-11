from __future__ import annotations

import json
import uuid
from typing import Any, Dict

from ..http import json_response
from ..keys import action_sk, book_sk, pk, stats_sk
from ..booklib import google_books_lookup, normalize_isbn
from ..models import ActionType
from ..parsing import parse_json_body, parse_year, querystring


def post_action(
    event: Dict[str, Any],
    *,
    origin: str,
    table: Any,
    now_iso: Any,
) -> Dict[str, Any]:
    data, err = parse_json_body(event)
    if err:
        return json_response(400, {"error": err}, origin=origin)

    year = parse_year(str(data.get("year")) if data.get("year") is not None else None)
    if year is None:
        return json_response(400, {"error": "year is required"}, origin=origin)

    action_type = ActionType.from_any(data.get("type"))
    if action_type is None:
        return json_response(400, {"error": "type must be BJJ|PILATES|SAVE|READ"}, origin=origin)

    ts = str(data.get("ts") or "").strip() or now_iso()
    # Keep ts in ISO format; if user sends something else we still store it, but it impacts sorting.
    action_id = uuid.uuid4().hex

    item: Dict[str, Any] = {
        "pk": pk(),
        "sk": action_sk(year, ts, action_id),
        "year": year,
        "ts": ts,
        "type": action_type.value,
        "createdAt": now_iso(),
    }

    # Stats increments
    inc_expr = ["updatedAt = :u"]
    inc_vals: Dict[str, Any] = {":u": now_iso()}
    inc_names: Dict[str, str] = {}
    add_parts = []

    if action_type == ActionType.BJJ:
        add_parts.append("#bjjCount :b")
        inc_names["#bjjCount"] = "bjjCount"
        inc_vals[":b"] = 1
    elif action_type == ActionType.PILATES:
        add_parts.append("#pilatesCount :p")
        inc_names["#pilatesCount"] = "pilatesCount"
        inc_vals[":p"] = 1
    elif action_type == ActionType.SAVE:
        amount_cents = data.get("amountCents")
        if not isinstance(amount_cents, int):
            return json_response(400, {"error": "SAVE requires integer amountCents"}, origin=origin)
        item["amountCents"] = amount_cents
        add_parts.append("#savedCentsTotal :s")
        inc_names["#savedCentsTotal"] = "savedCentsTotal"
        inc_vals[":s"] = amount_cents
    elif action_type == ActionType.READ:
        isbn = normalize_isbn(data.get("isbn"))
        if isbn is None:
            return json_response(400, {"error": "READ requires valid isbn (ISBN-10 or ISBN-13)"}, origin=origin)

        try:
            meta = google_books_lookup(isbn)
        except Exception:
            return json_response(502, {"error": "google_books_lookup_failed"}, origin=origin)
        if meta is None:
            return json_response(404, {"error": "book_not_found_for_isbn"}, origin=origin)

        item["isbn"] = isbn
        # Prefer referencing the persistent BOOK# item over duplicating book metadata on each action.
        item["bookSk"] = book_sk(isbn)

        # Upsert a persistent "library" record (deduped by ISBN).
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
        ]
        expr_vals: Dict[str, Any] = {":u": now, ":c": now, ":isbn": isbn, ":a": authors, ":gf": now}

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
        # Always persist the full Google `volumeInfo` payload when available.
        volume_info = meta.get("googleVolumeInfo")
        if isinstance(volume_info, dict) and volume_info:
            expr_parts.append("googleVolumeInfo = :gvi")
            expr_vals[":gvi"] = volume_info

        table.update_item(
            Key={"pk": pk(), "sk": book_sk(isbn)},
            UpdateExpression="SET " + ", ".join(expr_parts),
            ExpressionAttributeValues=expr_vals,
        )

        add_parts.append("#readBooksTotal :rb")
        add_parts.append("#readCount :rc")
        inc_names["#readBooksTotal"] = "readBooksTotal"
        inc_names["#readCount"] = "readCount"
        inc_vals[":rb"] = 1
        inc_vals[":rc"] = 1

    note = data.get("note")
    if note:
        item["note"] = str(note)

    table.put_item(Item=item)

    # Upsert stats row with atomic increments.
    update_expr = "SET " + ", ".join(inc_expr)
    if add_parts:
        update_expr += " ADD " + ", ".join(add_parts)

    update_kwargs: Dict[str, Any] = {
        "Key": {"pk": pk(), "sk": stats_sk(year)},
        "UpdateExpression": update_expr,
        "ExpressionAttributeValues": inc_vals,
    }
    if inc_names:
        update_kwargs["ExpressionAttributeNames"] = inc_names
    table.update_item(**update_kwargs)

    return json_response(201, {"action": {"year": year, "type": action_type.value, "ts": ts, "id": action_id}}, origin=origin)


def get_actions(event: Dict[str, Any], *, origin: str, table: Any) -> Dict[str, Any]:
    from boto3.dynamodb.conditions import Key  # type: ignore

    qs = querystring(event)
    year = parse_year(qs.get("year"))
    if year is None:
        return json_response(400, {"error": "year is required (e.g. ?year=2026)"}, origin=origin)

    action_type_filter = (qs.get("type") or "").strip().upper() or None
    limit_raw = qs.get("limit")
    try:
        limit = int(limit_raw) if limit_raw else 50
        limit = max(1, min(200, limit))
    except Exception:
        return json_response(400, {"error": "limit must be an integer"}, origin=origin)

    resp = table.query(
        KeyConditionExpression=Key("pk").eq(pk()) & Key("sk").begins_with(f"ACTION#{year}#"),
        ScanIndexForward=False,
        Limit=limit,
    )
    items = resp.get("Items") or []
    actions = []
    book_cache: Dict[str, Dict[str, Any]] = {}
    for it in items:
        if action_type_filter and it.get("type") != action_type_filter:
            continue
        isbn = it.get("isbn")
        book_title = it.get("bookTitle")
        book_authors = it.get("bookAuthors") or []

        # Back-compat: older actions stored duplicated book fields; newer actions store only references.
        if it.get("type") == ActionType.READ.value and isbn and (book_title is None or book_authors is None):
            if isbn not in book_cache:
                try:
                    res = table.get_item(Key={"pk": pk(), "sk": book_sk(str(isbn))})
                    b = res.get("Item") or {}
                    book_cache[isbn] = {"title": b.get("title"), "authors": b.get("authors") or []}
                except Exception:
                    book_cache[isbn] = {"title": None, "authors": []}
            book_title = book_title if book_title is not None else book_cache[isbn].get("title")
            if book_authors is None:
                book_authors = book_cache[isbn].get("authors") or []
        actions.append(
            {
                "year": int(it.get("year", year)),
                "type": it.get("type"),
                "ts": it.get("ts"),
                "amountCents": it.get("amountCents"),
                "isbn": isbn,
                "bookSk": it.get("bookSk") or (book_sk(str(isbn)) if isbn else None),
                "bookTitle": book_title,
                "bookAuthors": book_authors or [],
                "note": it.get("note"),
            }
        )
    return json_response(200, {"actions": actions}, origin=origin)

