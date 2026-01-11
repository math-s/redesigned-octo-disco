from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class FakeTable:
    put_items: List[Dict[str, Any]] = field(default_factory=list)
    update_calls: List[Dict[str, Any]] = field(default_factory=list)
    delete_calls: List[Dict[str, Any]] = field(default_factory=list)
    get_item_result: Dict[str, Any] = field(default_factory=dict)

    def get_item(self, **kwargs: Any) -> Dict[str, Any]:
        # Allow tests to pre-seed a return value.
        return dict(self.get_item_result)

    def put_item(self, **kwargs: Any) -> Dict[str, Any]:
        self.put_items.append(kwargs)
        return {}

    def update_item(self, **kwargs: Any) -> Dict[str, Any]:
        self.update_calls.append(kwargs)
        # Simulate "ALL_NEW" for goal patch by returning Attributes if provided by test.
        return {"Attributes": kwargs.get("_fake_attributes", {})}

    def delete_item(self, **kwargs: Any) -> Dict[str, Any]:
        self.delete_calls.append(kwargs)
        return {}


def make_event(
    *,
    method: str = "GET",
    path: str = "/",
    body: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    query: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    ev: Dict[str, Any] = {
        "rawPath": path,
        "requestContext": {"http": {"method": method}},
        "headers": headers or {},
        "queryStringParameters": query or None,
        "isBase64Encoded": False,
    }
    if body is not None:
        ev["body"] = json.dumps(body)
    return ev

