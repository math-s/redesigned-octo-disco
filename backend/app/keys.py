from __future__ import annotations


def pk() -> str:
    return "USER#me"


def goal_sk(year: int, goal_id: str) -> str:
    return f"GOAL#{year}#{goal_id}"


def action_sk(year: int, ts_iso: str, action_id: str) -> str:
    # Include timestamp for chronological sorting.
    return f"ACTION#{year}#{ts_iso}#{action_id}"


def stats_sk(year: int) -> str:
    return f"STATS#{year}"

