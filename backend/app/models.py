from __future__ import annotations

from enum import Enum
from typing import Any, Optional


class ActionType(str, Enum):
    BJJ = "BJJ"
    READ = "READ"
    SAVE = "SAVE"

    @classmethod
    def from_any(cls, value: Any) -> Optional["ActionType"]:
        if value is None:
            return None
        s = str(value).strip()
        if not s:
            return None
        s = s.upper()
        try:
            return cls(s)
        except Exception:
            return None


class GoalStatus(str, Enum):
    TODO = "todo"
    DOING = "doing"
    DONE = "done"

    @classmethod
    def from_any(cls, value: Any) -> Optional["GoalStatus"]:
        if value is None:
            return None
        s = str(value).strip()
        if not s:
            return None
        s = s.lower()
        try:
            return cls(s)
        except Exception:
            return None

