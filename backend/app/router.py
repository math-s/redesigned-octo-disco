from __future__ import annotations

from typing import Any, Dict

from .http import json_response
from .parsing import method as get_method
from .parsing import path as get_path
from .routes.actions import get_actions, post_action
from .routes.goals import delete_goal, get_goals, patch_goal, post_goal
from .routes.stats import get_stats


def dispatch(
    event: Dict[str, Any],
    *,
    origin: str,
    table: Any,
    now_iso: Any,
) -> Dict[str, Any]:
    m = get_method(event)
    p = get_path(event)

    if m == "GET" and p == "/stats":
        return get_stats(event, origin=origin, table=table)
    if m == "GET" and p == "/goals":
        return get_goals(event, origin=origin, table=table)
    if m == "POST" and p == "/goals":
        return post_goal(event, origin=origin, table=table, now_iso=now_iso)
    if m == "PATCH" and p.startswith("/goals/"):
        goal_id = p.split("/goals/", 1)[1].strip("/")
        return patch_goal(event, goal_id, origin=origin, table=table, now_iso=now_iso)
    if m == "DELETE" and p.startswith("/goals/"):
        goal_id = p.split("/goals/", 1)[1].strip("/")
        return delete_goal(event, goal_id, origin=origin, table=table)

    if m == "POST" and p == "/actions":
        return post_action(event, origin=origin, table=table, now_iso=now_iso)
    if m == "GET" and p == "/actions":
        return get_actions(event, origin=origin, table=table)

    return json_response(404, {"error": "not_found"}, origin=origin)

