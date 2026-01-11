from __future__ import annotations

import traceback
from typing import Any, Dict

from app.auth import require_admin_token
from app.config import get_env
from app.db import get_table
from app.http import json_response, options_response, origin_from_event
from app.parsing import method as get_method
from app.parsing import path as get_path
from app.router import dispatch
from app.timeutil import now_iso


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    origin = origin_from_event(event)
    request_id = getattr(context, "aws_request_id", None)
    try:
        method = get_method(event)
        path = get_path(event)

        if method == "OPTIONS":
            return options_response(origin=origin)

        if path == "/health":
            return json_response(200, {"ok": True}, origin=origin)

        if not require_admin_token(event):
            return json_response(401, {"error": "unauthorized"}, origin=origin)

        table = get_table(get_env("TABLE_NAME"))
        return dispatch(event, origin=origin, table=table, now_iso=now_iso)
    except Exception as exc:
        # CloudWatch logs: exception + stack trace for debugging.
        print("Unhandled exception", {"requestId": request_id, "error": repr(exc)})
        print(traceback.format_exc())
        return json_response(500, {"error": "internal_server_error", "requestId": request_id}, origin=origin)
