from __future__ import annotations

from typing import Any, Dict

from .config import get_env


def require_admin_token(event: Dict[str, Any]) -> bool:
    expected = get_env("ADMIN_TOKEN", "")
    if not expected:
        # If you truly want no auth, set ADMIN_TOKEN to empty and this will allow requests.
        return True
    headers = event.get("headers") or {}
    got = headers.get("x-admin-token") or headers.get("X-Admin-Token")
    return got == expected

