from __future__ import annotations

import json
from decimal import Decimal

from app.routes.actions import get_actions

from .conftest import FakeTable, make_event


def test_get_actions_serializes_decimals_from_dynamodb():
    # DynamoDB (via boto3) commonly returns number attributes as Decimal.
    table = FakeTable()
    table.query_result = {
        "Items": [
            {"year": 2026, "type": "READ", "ts": "2026-01-01T00:00:00+00:00", "pages": Decimal("10")},
            {"year": 2026, "type": "SAVE", "ts": "2026-01-02T00:00:00+00:00", "amountCents": Decimal("1234")},
        ]
    }

    resp = get_actions(
        make_event(method="GET", path="/actions", query={"year": "2026", "limit": "30"}),
        origin="*",
        table=table,
    )

    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body["actions"][0]["pages"] == 10
    assert body["actions"][1]["amountCents"] == 1234

