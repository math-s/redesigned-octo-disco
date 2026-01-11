from __future__ import annotations

import uuid
from typing import Any, Dict

from ..http import json_response
from ..keys import action_sk, pk, stats_sk
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
        return json_response(400, {"error": "type must be BJJ|SAVE|READ"}, origin=origin)

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
    elif action_type == ActionType.SAVE:
        amount_cents = data.get("amountCents")
        if not isinstance(amount_cents, int):
            return json_response(400, {"error": "SAVE requires integer amountCents"}, origin=origin)
        item["amountCents"] = amount_cents
        add_parts.append("#savedCentsTotal :s")
        inc_names["#savedCentsTotal"] = "savedCentsTotal"
        inc_vals[":s"] = amount_cents
    elif action_type == ActionType.READ:
        pages = data.get("pages", 0)
        if pages is None:
            pages = 0
        if not isinstance(pages, int) or pages < 0:
            return json_response(400, {"error": "READ pages must be a non-negative integer"}, origin=origin)
        book = data.get("book")
        if book is not None:
            item["book"] = str(book)
        item["pages"] = pages
        add_parts.append("#readPagesTotal :p")
        add_parts.append("#readCount :rc")
        inc_names["#readPagesTotal"] = "readPagesTotal"
        inc_names["#readCount"] = "readCount"
        inc_vals[":p"] = pages
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
    for it in items:
        if action_type_filter and it.get("type") != action_type_filter:
            continue
        actions.append(
            {
                "year": int(it.get("year", year)),
                "type": it.get("type"),
                "ts": it.get("ts"),
                "amountCents": it.get("amountCents"),
                "pages": it.get("pages"),
                "book": it.get("book"),
                "note": it.get("note"),
            }
        )
    return json_response(200, {"actions": actions}, origin=origin)

