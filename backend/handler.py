import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

import boto3
from boto3.dynamodb.conditions import Key


ddb = boto3.resource("dynamodb")


def _env(name: str, default: Optional[str] = None) -> str:
    val = os.environ.get(name, default)
    if val is None:
        raise RuntimeError(f"Missing required env var: {name}")
    return val


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _json(status_code: int, body: Dict[str, Any], *, origin: str) -> Dict[str, Any]:
    return {
        "statusCode": status_code,
        "headers": {
            "content-type": "application/json; charset=utf-8",
            "access-control-allow-origin": origin,
            "access-control-allow-headers": "content-type,x-admin-token",
            "access-control-allow-methods": "GET,POST,PATCH,DELETE,OPTIONS",
            "cache-control": "no-store",
        },
        "body": json.dumps(body, separators=(",", ":"), ensure_ascii=False),
    }


def _origin_from_event(event: Dict[str, Any]) -> str:
    allowed = os.environ.get("ALLOWED_ORIGIN", "*").strip() or "*"
    if allowed == "*":
        return "*"
    req_origin = (event.get("headers") or {}).get("origin") or (event.get("headers") or {}).get("Origin")
    return allowed if req_origin == allowed else allowed


def _parse_json_body(event: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
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


def _require_token(event: Dict[str, Any]) -> bool:
    expected = _env("ADMIN_TOKEN", "")
    if not expected:
        # If you truly want no auth, set ADMIN_TOKEN to empty and this will allow requests.
        return True
    headers = event.get("headers") or {}
    got = headers.get("x-admin-token") or headers.get("X-Admin-Token")
    return got == expected


def _table():
    return ddb.Table(_env("TABLE_NAME"))


def _querystring(event: Dict[str, Any]) -> Dict[str, str]:
    qs = event.get("queryStringParameters") or {}
    return {k: v for k, v in qs.items() if v is not None}


def _path(event: Dict[str, Any]) -> str:
    return event.get("rawPath") or event.get("path") or "/"


def _method(event: Dict[str, Any]) -> str:
    ctx = event.get("requestContext") or {}
    http = ctx.get("http") or {}
    m = http.get("method") or event.get("httpMethod") or "GET"
    return m.upper()


def _pk() -> str:
    return "USER#me"


def _goal_sk(year: int, goal_id: str) -> str:
    return f"GOAL#{year}#{goal_id}"


def _action_sk(year: int, ts_iso: str, action_id: str) -> str:
    # Include timestamp for chronological sorting.
    return f"ACTION#{year}#{ts_iso}#{action_id}"


def _stats_sk(year: int) -> str:
    return f"STATS#{year}"


def _parse_year(value: Optional[str]) -> Optional[int]:
    if value is None:
        return None
    try:
        y = int(value)
        if y < 1970 or y > 3000:
            return None
        return y
    except Exception:
        return None


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    origin = _origin_from_event(event)
    method = _method(event)
    path = _path(event)

    if method == "OPTIONS":
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

    if path == "/health":
        return _json(200, {"ok": True}, origin=origin)

    if not _require_token(event):
        return _json(401, {"error": "unauthorized"}, origin=origin)

    # --- Routes ---
    if method == "GET" and path == "/stats":
        return _get_stats(event, origin=origin)
    if method == "GET" and path == "/goals":
        return _get_goals(event, origin=origin)
    if method == "POST" and path == "/goals":
        return _post_goal(event, origin=origin)
    if method == "PATCH" and path.startswith("/goals/"):
        goal_id = path.split("/goals/", 1)[1].strip("/")
        return _patch_goal(event, goal_id, origin=origin)
    if method == "DELETE" and path.startswith("/goals/"):
        goal_id = path.split("/goals/", 1)[1].strip("/")
        return _delete_goal(event, goal_id, origin=origin)

    if method == "POST" and path == "/actions":
        return _post_action(event, origin=origin)
    if method == "GET" and path == "/actions":
        return _get_actions(event, origin=origin)

    return _json(404, {"error": "not_found"}, origin=origin)


def _get_stats(event: Dict[str, Any], *, origin: str) -> Dict[str, Any]:
    qs = _querystring(event)
    year = _parse_year(qs.get("year"))
    if year is None:
        return _json(400, {"error": "year is required (e.g. ?year=2026)"}, origin=origin)

    res = _table().get_item(Key={"pk": _pk(), "sk": _stats_sk(year)})
    item = res.get("Item") or {}
    stats = {
        "year": year,
        "bjjCount": int(item.get("bjjCount", 0)),
        "savedCentsTotal": int(item.get("savedCentsTotal", 0)),
        "readPagesTotal": int(item.get("readPagesTotal", 0)),
        "readCount": int(item.get("readCount", 0)),
        "updatedAt": item.get("updatedAt"),
    }
    return _json(200, {"stats": stats}, origin=origin)


def _get_goals(event: Dict[str, Any], *, origin: str) -> Dict[str, Any]:
    qs = _querystring(event)
    year = _parse_year(qs.get("year"))
    if year is None:
        return _json(400, {"error": "year is required (e.g. ?year=2026)"}, origin=origin)

    resp = _table().query(
        KeyConditionExpression=Key("pk").eq(_pk()) & Key("sk").begins_with(f"GOAL#{year}#"),
    )
    items = resp.get("Items") or []
    goals = []
    for it in items:
        _, _, goal_id = (it.get("sk", "GOAL#0#").split("#", 2) + [""])[:3]
        goals.append(
            {
                "id": goal_id,
                "year": int(it.get("year", year)),
                "title": it.get("title", ""),
                "status": it.get("status", "todo"),
                "target": it.get("target"),
                "createdAt": it.get("createdAt"),
                "updatedAt": it.get("updatedAt"),
            }
        )
    goals.sort(key=lambda g: (g.get("status") != "done", g.get("createdAt") or ""))
    return _json(200, {"goals": goals}, origin=origin)


def _post_goal(event: Dict[str, Any], *, origin: str) -> Dict[str, Any]:
    data, err = _parse_json_body(event)
    if err:
        return _json(400, {"error": err}, origin=origin)

    year = _parse_year(str(data.get("year")) if data.get("year") is not None else None)
    title = (data.get("title") or "").strip()
    status = (data.get("status") or "todo").strip()
    target = data.get("target")

    if year is None:
        return _json(400, {"error": "year is required"}, origin=origin)
    if not title:
        return _json(400, {"error": "title is required"}, origin=origin)
    if status not in ("todo", "doing", "done"):
        return _json(400, {"error": "status must be todo|doing|done"}, origin=origin)

    goal_id = uuid.uuid4().hex
    now = _now_iso()
    item = {
        "pk": _pk(),
        "sk": _goal_sk(year, goal_id),
        "year": year,
        "title": title,
        "status": status,
        "createdAt": now,
        "updatedAt": now,
    }
    if target is not None:
        item["target"] = target

    _table().put_item(Item=item)
    return _json(201, {"goal": {"id": goal_id, "year": year, "title": title, "status": status, "target": target}}, origin=origin)


def _patch_goal(event: Dict[str, Any], goal_id: str, *, origin: str) -> Dict[str, Any]:
    if not goal_id:
        return _json(400, {"error": "goalId is required"}, origin=origin)
    data, err = _parse_json_body(event)
    if err:
        return _json(400, {"error": err}, origin=origin)

    year = _parse_year(str(data.get("year")) if data.get("year") is not None else None)
    if year is None:
        return _json(400, {"error": "year is required"}, origin=origin)

    patch = data.get("patch") or {}
    if not isinstance(patch, dict):
        return _json(400, {"error": "patch must be an object"}, origin=origin)

    allowed: Dict[str, Any] = {}
    if "title" in patch:
        allowed["title"] = str(patch.get("title") or "").strip()
    if "status" in patch:
        allowed["status"] = str(patch.get("status") or "").strip()
    if "target" in patch:
        allowed["target"] = patch.get("target")

    if "status" in allowed and allowed["status"] not in ("todo", "doing", "done"):
        return _json(400, {"error": "status must be todo|doing|done"}, origin=origin)
    if "title" in allowed and not allowed["title"]:
        return _json(400, {"error": "title cannot be empty"}, origin=origin)

    if not allowed:
        return _json(400, {"error": "no valid fields to patch"}, origin=origin)

    now = _now_iso()
    expr_parts = ["updatedAt = :u"]
    expr_vals: Dict[str, Any] = {":u": now}
    expr_names: Dict[str, str] = {}

    for k, v in allowed.items():
        name = f"#{k}"
        val = f":{k}"
        expr_names[name] = k
        expr_vals[val] = v
        expr_parts.append(f"{name} = {val}")

    resp = _table().update_item(
        Key={"pk": _pk(), "sk": _goal_sk(year, goal_id)},
        UpdateExpression="SET " + ", ".join(expr_parts),
        ExpressionAttributeNames=expr_names,
        ExpressionAttributeValues=expr_vals,
        ReturnValues="ALL_NEW",
    )

    item = resp.get("Attributes") or {}
    return _json(
        200,
        {
            "goal": {
                "id": goal_id,
                "year": year,
                "title": item.get("title", ""),
                "status": item.get("status", "todo"),
                "target": item.get("target"),
                "updatedAt": item.get("updatedAt"),
            }
        },
        origin=origin,
    )


def _delete_goal(event: Dict[str, Any], goal_id: str, *, origin: str) -> Dict[str, Any]:
    qs = _querystring(event)
    year = _parse_year(qs.get("year"))
    if year is None:
        return _json(400, {"error": "year is required (e.g. ?year=2026)"}, origin=origin)
    if not goal_id:
        return _json(400, {"error": "goalId is required"}, origin=origin)

    _table().delete_item(Key={"pk": _pk(), "sk": _goal_sk(year, goal_id)})
    return _json(200, {"ok": True}, origin=origin)


def _post_action(event: Dict[str, Any], *, origin: str) -> Dict[str, Any]:
    data, err = _parse_json_body(event)
    if err:
        return _json(400, {"error": err}, origin=origin)

    year = _parse_year(str(data.get("year")) if data.get("year") is not None else None)
    if year is None:
        return _json(400, {"error": "year is required"}, origin=origin)

    action_type = str(data.get("type") or "").strip().upper()
    if action_type not in ("BJJ", "SAVE", "READ"):
        return _json(400, {"error": "type must be BJJ|SAVE|READ"}, origin=origin)

    ts = str(data.get("ts") or "").strip() or _now_iso()
    # Keep ts in ISO format; if user sends something else we still store it, but it impacts sorting.
    action_id = uuid.uuid4().hex

    item: Dict[str, Any] = {
        "pk": _pk(),
        "sk": _action_sk(year, ts, action_id),
        "year": year,
        "ts": ts,
        "type": action_type,
        "createdAt": _now_iso(),
    }

    # Stats increments
    inc_expr = ["updatedAt = :u"]
    inc_vals: Dict[str, Any] = {":u": _now_iso()}
    inc_names: Dict[str, str] = {}
    add_parts = []

    if action_type == "BJJ":
        add_parts.append("#bjjCount :b")
        inc_names["#bjjCount"] = "bjjCount"
        inc_vals[":b"] = 1
    elif action_type == "SAVE":
        amount_cents = data.get("amountCents")
        if not isinstance(amount_cents, int):
            return _json(400, {"error": "SAVE requires integer amountCents"}, origin=origin)
        item["amountCents"] = amount_cents
        add_parts.append("#savedCentsTotal :s")
        inc_names["#savedCentsTotal"] = "savedCentsTotal"
        inc_vals[":s"] = amount_cents
    elif action_type == "READ":
        pages = data.get("pages", 0)
        if pages is None:
            pages = 0
        if not isinstance(pages, int) or pages < 0:
            return _json(400, {"error": "READ pages must be a non-negative integer"}, origin=origin)
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

    tbl = _table()
    tbl.put_item(Item=item)

    # Upsert stats row with atomic increments.
    update_expr = "SET " + ", ".join(inc_expr)
    if add_parts:
        update_expr += " ADD " + ", ".join(add_parts)

    update_kwargs: Dict[str, Any] = {
        "Key": {"pk": _pk(), "sk": _stats_sk(year)},
        "UpdateExpression": update_expr,
        "ExpressionAttributeValues": inc_vals,
    }
    if inc_names:
        update_kwargs["ExpressionAttributeNames"] = inc_names
    tbl.update_item(**update_kwargs)

    return _json(201, {"action": {"year": year, "type": action_type, "ts": ts, "id": action_id}}, origin=origin)


def _get_actions(event: Dict[str, Any], *, origin: str) -> Dict[str, Any]:
    qs = _querystring(event)
    year = _parse_year(qs.get("year"))
    if year is None:
        return _json(400, {"error": "year is required (e.g. ?year=2026)"}, origin=origin)
    action_type = (qs.get("type") or "").strip().upper() or None
    limit_raw = qs.get("limit")
    try:
        limit = int(limit_raw) if limit_raw else 50
        limit = max(1, min(200, limit))
    except Exception:
        return _json(400, {"error": "limit must be an integer"}, origin=origin)

    resp = _table().query(
        KeyConditionExpression=Key("pk").eq(_pk()) & Key("sk").begins_with(f"ACTION#{year}#"),
        ScanIndexForward=False,
        Limit=limit,
    )
    items = resp.get("Items") or []
    actions = []
    for it in items:
        if action_type and it.get("type") != action_type:
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
    return _json(200, {"actions": actions}, origin=origin)
