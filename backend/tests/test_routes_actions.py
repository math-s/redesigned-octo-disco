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


def test_post_action_pilates_happy_path():
    table = FakeTable()

    resp = post_action(
        make_event(method="POST", path="/actions", body={"year": 2026, "type": "PILATES"}),
        origin="*",
        table=table,
        now_iso=lambda: "2026-01-01T00:00:00+00:00",
    )

    assert resp["statusCode"] == 201
    body = json.loads(resp["body"])
    assert body["action"]["type"] == "PILATES"
    assert len(table.put_items) == 1
    assert len(table.update_calls) == 1


def test_post_action_read_requires_valid_isbn():
    table = FakeTable()

    resp = post_action(
        make_event(method="POST", path="/actions", body={"year": 2026, "type": "READ", "isbn": "not-an-isbn"}),
        origin="*",
        table=table,
        now_iso=lambda: "2026-01-01T00:00:00+00:00",
    )

    assert resp["statusCode"] == 400
    assert json.loads(resp["body"])["error"] == "READ requires valid isbn (ISBN-10 or ISBN-13)"
    assert len(table.put_items) == 0
    assert len(table.update_calls) == 0


def test_post_action_read_happy_path_looks_up_book(monkeypatch):
    # Avoid real network calls in unit tests.
    from app.routes import actions as actions_mod

    monkeypatch.setattr(
        actions_mod,
        "_google_books_lookup",
        lambda isbn: {
            "googleVolumeId": "vol_123",
            "title": "The Example Book",
            "authors": ["Jane Doe"],
            "publishedDate": "2020",
            "pageCount": 123,
            "categories": ["Nonfiction"],
            "thumbnail": "https://example.com/t.png",
        },
    )

    table = FakeTable()
    resp = post_action(
        make_event(method="POST", path="/actions", body={"year": 2026, "type": "READ", "isbn": "978-0132350884"}),
        origin="*",
        table=table,
        now_iso=lambda: "2026-01-01T00:00:00+00:00",
    )

    assert resp["statusCode"] == 201
    assert len(table.put_items) == 1
    # One update for BOOK upsert + one update for STATS increment
    assert len(table.update_calls) == 2

