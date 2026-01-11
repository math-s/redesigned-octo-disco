from __future__ import annotations

import json
import os

import handler as lambda_handler

from .conftest import FakeTable, make_event


def test_handler_options():
    os.environ["TABLE_NAME"] = "ignored"
    os.environ["ADMIN_TOKEN"] = ""
    os.environ["ALLOWED_ORIGIN"] = "*"

    resp = lambda_handler.handler(make_event(method="OPTIONS", path="/anything"), None)
    assert resp["statusCode"] == 204


def test_handler_health():
    os.environ["TABLE_NAME"] = "ignored"
    os.environ["ADMIN_TOKEN"] = ""
    os.environ["ALLOWED_ORIGIN"] = "*"

    resp = lambda_handler.handler(make_event(method="GET", path="/health"), None)
    assert resp["statusCode"] == 200
    assert json.loads(resp["body"]) == {"ok": True}


def test_handler_dispatches_route(monkeypatch):
    os.environ["TABLE_NAME"] = "tbl"
    os.environ["ADMIN_TOKEN"] = ""
    os.environ["ALLOWED_ORIGIN"] = "*"

    table = FakeTable()
    monkeypatch.setattr(lambda_handler, "get_table", lambda _: table)

    resp = lambda_handler.handler(make_event(method="POST", path="/actions", body={"year": 2026, "type": "BJJ"}), None)
    assert resp["statusCode"] == 201
    assert len(table.put_items) == 1

