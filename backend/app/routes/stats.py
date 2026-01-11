from __future__ import annotations

from typing import Any, Dict

from ..http import json_response
from ..keys import pk, stats_sk
from ..parsing import parse_year, querystring


def get_stats(event: Dict[str, Any], *, origin: str, table: Any) -> Dict[str, Any]:
    qs = querystring(event)
    year = parse_year(qs.get("year"))
    if year is None:
        return json_response(400, {"error": "year is required (e.g. ?year=2026)"}, origin=origin)

    res = table.get_item(Key={"pk": pk(), "sk": stats_sk(year)})
    item = res.get("Item") or {}
    stats = {
        "year": year,
        "bjjCount": int(item.get("bjjCount", 0)),
        "savedCentsTotal": int(item.get("savedCentsTotal", 0)),
        "readBooksTotal": int(item.get("readBooksTotal", 0)),
        "readCount": int(item.get("readCount", 0)),
        "updatedAt": item.get("updatedAt"),
    }
    return json_response(200, {"stats": stats}, origin=origin)

