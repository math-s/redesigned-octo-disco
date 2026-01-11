from __future__ import annotations

import uuid
from typing import Any, Dict

from ..http import json_response
from ..keys import goal_sk, pk
from ..models import GoalKind, GoalStatus
from ..parsing import parse_json_body, parse_year, querystring


def get_goals(event: Dict[str, Any], *, origin: str, table: Any) -> Dict[str, Any]:
    from boto3.dynamodb.conditions import Key  # type: ignore

    qs = querystring(event)
    year = parse_year(qs.get("year"))
    if year is None:
        return json_response(400, {"error": "year is required (e.g. ?year=2026)"}, origin=origin)

    resp = table.query(
        KeyConditionExpression=Key("pk").eq(pk()) & Key("sk").begins_with(f"GOAL#{year}#"),
    )
    items = resp.get("Items") or []
    goals = []
    for it in items:
        _, _, goal_id = (str(it.get("sk", "GOAL#0#")).split("#", 2) + [""])[:3]
        goals.append(
            {
                "id": goal_id,
                "year": int(it.get("year", year)),
                "title": it.get("title", ""),
                "kind": it.get("kind"),
                "status": it.get("status", GoalStatus.TODO.value),
                "target": it.get("target"),
                "createdAt": it.get("createdAt"),
                "updatedAt": it.get("updatedAt"),
            }
        )
    goals.sort(key=lambda g: (g.get("status") != GoalStatus.DONE.value, g.get("createdAt") or ""))
    return json_response(200, {"goals": goals}, origin=origin)


def post_goal(
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
    kind = GoalKind.from_any(data.get("kind"))
    title = (data.get("title") or "").strip()
    status = GoalStatus.from_any(data.get("status")) or GoalStatus.TODO
    target = data.get("target")

    if year is None:
        return json_response(400, {"error": "year is required"}, origin=origin)
    if data.get("status") is not None and GoalStatus.from_any(data.get("status")) is None:
        return json_response(400, {"error": "status must be todo|doing|done"}, origin=origin)

    # Structured goals (preferred): kind + numeric target.
    if kind is not None:
        if not isinstance(target, int) or target <= 0:
            return json_response(400, {"error": "target must be a positive integer"}, origin=origin)
        # Title can be omitted for structured goals; the frontend can render from kind/target.
        if not title:
            title = kind.value
    else:
        # Legacy free-text goal support.
        if not title:
            return json_response(400, {"error": "title is required"}, origin=origin)

    goal_id = uuid.uuid4().hex
    now = now_iso()
    item: Dict[str, Any] = {
        "pk": pk(),
        "sk": goal_sk(year, goal_id),
        "year": year,
        "title": title,
        "status": status.value,
        "createdAt": now,
        "updatedAt": now,
    }
    if kind is not None:
        item["kind"] = kind.value
    if target is not None:
        item["target"] = target

    table.put_item(Item=item)
    return json_response(
        201,
        {
            "goal": {
                "id": goal_id,
                "year": year,
                "title": title,
                "kind": kind.value if kind is not None else None,
                "status": status.value,
                "target": target,
            }
        },
        origin=origin,
    )


def patch_goal(
    event: Dict[str, Any],
    goal_id: str,
    *,
    origin: str,
    table: Any,
    now_iso: Any,
) -> Dict[str, Any]:
    if not goal_id:
        return json_response(400, {"error": "goalId is required"}, origin=origin)
    data, err = parse_json_body(event)
    if err:
        return json_response(400, {"error": err}, origin=origin)

    year = parse_year(str(data.get("year")) if data.get("year") is not None else None)
    if year is None:
        return json_response(400, {"error": "year is required"}, origin=origin)

    patch = data.get("patch") or {}
    if not isinstance(patch, dict):
        return json_response(400, {"error": "patch must be an object"}, origin=origin)

    allowed: Dict[str, Any] = {}
    if "title" in patch:
        allowed["title"] = str(patch.get("title") or "").strip()
    if "kind" in patch:
        parsed = GoalKind.from_any(patch.get("kind"))
        if parsed is None:
            return json_response(
                400,
                {"error": "kind must be BJJ_SESSIONS|MONEY_SAVED_CENTS|BOOKS_FINISHED"},
                origin=origin,
            )
        allowed["kind"] = parsed.value
    if "status" in patch:
        parsed = GoalStatus.from_any(patch.get("status"))
        if parsed is None:
            return json_response(400, {"error": "status must be todo|doing|done"}, origin=origin)
        allowed["status"] = parsed.value
    if "target" in patch:
        tgt = patch.get("target")
        if not isinstance(tgt, int) or tgt <= 0:
            return json_response(400, {"error": "target must be a positive integer"}, origin=origin)
        allowed["target"] = tgt

    if "title" in allowed and not allowed["title"]:
        return json_response(400, {"error": "title cannot be empty"}, origin=origin)

    if not allowed:
        return json_response(400, {"error": "no valid fields to patch"}, origin=origin)

    now = now_iso()
    expr_parts = ["updatedAt = :u"]
    expr_vals: Dict[str, Any] = {":u": now}
    expr_names: Dict[str, str] = {}

    for k, v in allowed.items():
        name = f"#{k}"
        val = f":{k}"
        expr_names[name] = k
        expr_vals[val] = v
        expr_parts.append(f"{name} = {val}")

    resp = table.update_item(
        Key={"pk": pk(), "sk": goal_sk(year, goal_id)},
        UpdateExpression="SET " + ", ".join(expr_parts),
        ExpressionAttributeNames=expr_names,
        ExpressionAttributeValues=expr_vals,
        ReturnValues="ALL_NEW",
    )

    item = resp.get("Attributes") or {}
    return json_response(
        200,
        {
            "goal": {
                "id": goal_id,
                "year": year,
                "title": item.get("title", ""),
                "kind": item.get("kind"),
                "status": item.get("status", GoalStatus.TODO.value),
                "target": item.get("target"),
                "updatedAt": item.get("updatedAt"),
            }
        },
        origin=origin,
    )


def delete_goal(event: Dict[str, Any], goal_id: str, *, origin: str, table: Any) -> Dict[str, Any]:
    qs = querystring(event)
    year = parse_year(qs.get("year"))
    if year is None:
        return json_response(400, {"error": "year is required (e.g. ?year=2026)"}, origin=origin)
    if not goal_id:
        return json_response(400, {"error": "goalId is required"}, origin=origin)

    table.delete_item(Key={"pk": pk(), "sk": goal_sk(year, goal_id)})
    return json_response(200, {"ok": True}, origin=origin)

