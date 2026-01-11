from __future__ import annotations

import json

from app.routes.goals import delete_goal, patch_goal, post_goal

from .conftest import FakeTable, make_event


def test_post_goal_defaults_status_to_todo():
    table = FakeTable()

    resp = post_goal(
        make_event(method="POST", path="/goals", body={"year": 2026, "title": "Train more"}),
        origin="*",
        table=table,
        now_iso=lambda: "2026-01-01T00:00:00+00:00",
    )

    assert resp["statusCode"] == 201
    body = json.loads(resp["body"])
    assert body["goal"]["status"] == "todo"
    assert len(table.put_items) == 1


def test_patch_goal_validates_status():
    table = FakeTable()

    resp = patch_goal(
        make_event(method="PATCH", path="/goals/abc", body={"year": 2026, "patch": {"status": "nope"}}),
        "abc",
        origin="*",
        table=table,
        now_iso=lambda: "2026-01-01T00:00:00+00:00",
    )

    assert resp["statusCode"] == 400
    assert json.loads(resp["body"])["error"] == "status must be todo|doing|done"
    assert len(table.update_calls) == 0


def test_delete_goal_requires_year_query_param():
    table = FakeTable()

    resp = delete_goal(
        make_event(method="DELETE", path="/goals/abc", query={}),
        "abc",
        origin="*",
        table=table,
    )

    assert resp["statusCode"] == 400
    assert json.loads(resp["body"])["error"].startswith("year is required")
    assert len(table.delete_calls) == 0

