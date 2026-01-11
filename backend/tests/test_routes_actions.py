from __future__ import annotations

import json

from app.routes.actions import post_action

from .conftest import FakeTable, make_event


def test_post_action_bjj_happy_path():
    table = FakeTable()

    resp = post_action(
        make_event(method="POST", path="/actions", body={"year": 2026, "type": "BJJ"}),
        origin="*",
        table=table,
        now_iso=lambda: "2026-01-01T00:00:00+00:00",
    )

    assert resp["statusCode"] == 201
    body = json.loads(resp["body"])
    assert body["action"]["type"] == "BJJ"
    assert len(table.put_items) == 1
    assert len(table.update_calls) == 1


def test_post_action_read_validates_pages():
    table = FakeTable()

    resp = post_action(
        make_event(method="POST", path="/actions", body={"year": 2026, "type": "READ", "pages": -1}),
        origin="*",
        table=table,
        now_iso=lambda: "2026-01-01T00:00:00+00:00",
    )

    assert resp["statusCode"] == 400
    assert json.loads(resp["body"])["error"] == "READ pages must be a non-negative integer"
    assert len(table.put_items) == 0
    assert len(table.update_calls) == 0

