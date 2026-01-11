from __future__ import annotations

import json

from app.routes.books import post_book

from .conftest import FakeTable, make_event


def test_post_book_requires_isbn():
    table = FakeTable()

    resp = post_book(
        make_event(method="POST", path="/books", body={}),
        origin="*",
        table=table,
        now_iso=lambda: "2026-01-01T00:00:00+00:00",
    )

    assert resp["statusCode"] == 400
    assert json.loads(resp["body"])["error"] == "isbn is required (ISBN-10 or ISBN-13)"
    assert len(table.update_calls) == 0


def test_post_book_happy_path_looks_up_book(monkeypatch):
    # Avoid real network calls in unit tests.
    from app.routes import books as books_mod

    monkeypatch.setattr(
        books_mod,
        "google_books_lookup",
        lambda isbn: {
            "googleVolumeId": "vol_123",
            "googleVolumeInfo": {"title": "The Example Book"},
            "title": "The Example Book",
            "authors": ["Jane Doe"],
            "publishedDate": "2020",
            "pageCount": 123,
            "categories": ["Nonfiction"],
            "thumbnail": "https://example.com/t.png",
        },
    )

    table = FakeTable()
    resp = post_book(
        make_event(method="POST", path="/books", body={"isbn": "978-0132350884"}),
        origin="*",
        table=table,
        now_iso=lambda: "2026-01-01T00:00:00+00:00",
    )

    assert resp["statusCode"] == 201
    assert len(table.update_calls) == 1

