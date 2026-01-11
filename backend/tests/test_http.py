from __future__ import annotations

import json
from decimal import Decimal

from app.http import json_response


def test_json_response_serializes_decimal():
    resp = json_response(200, {"x": Decimal("12"), "y": Decimal("1.5")}, origin="*")
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body == {"x": 12, "y": 1.5}

