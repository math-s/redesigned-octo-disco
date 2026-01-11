from __future__ import annotations

import json
import re
from typing import Any, Dict


_ISBN_RE = re.compile(r"^[0-9X]+$")


def normalize_isbn(value: Any) -> str | None:
    if value is None:
        return None
    s = str(value).strip().upper()
    if not s:
        return None
    # Common formatting: hyphens/spaces.
    s = s.replace("-", "").replace(" ", "")
    if not _ISBN_RE.match(s):
        return None
    if len(s) == 13 and s.isdigit():
        return s
    if len(s) == 10 and s[:9].isdigit() and (s[9].isdigit() or s[9] == "X"):
        return s
    return None


def google_books_lookup(isbn: str) -> Dict[str, Any] | None:
    """
    Returns a subset of Google Books volume fields for a given ISBN,
    plus the full `volumeInfo` payload for persistence.
    """
    from urllib.request import Request, urlopen

    url = f"https://www.googleapis.com/books/v1/volumes?q=isbn:{isbn}"
    req = Request(url, headers={"accept": "application/json", "user-agent": "yeargoals/1.0"})
    with urlopen(req, timeout=8) as resp:  # nosec - controlled URL; used for public metadata fetch
        raw = resp.read().decode("utf-8", errors="replace")
    data = json.loads(raw or "{}")
    items = data.get("items") or []
    if not items:
        return None
    first = items[0] or {}
    volume_info = first.get("volumeInfo") or {}
    if not isinstance(volume_info, dict):
        volume_info = {}

    title = volume_info.get("title")
    authors = volume_info.get("authors") or []
    if not isinstance(authors, list):
        authors = []
    authors = [str(a) for a in authors if str(a).strip()]

    image_links = volume_info.get("imageLinks") or {}
    thumbnail = image_links.get("thumbnail") or image_links.get("smallThumbnail")

    categories = volume_info.get("categories") or []
    if not isinstance(categories, list):
        categories = []
    categories = [str(c) for c in categories if str(c).strip()]

    out: Dict[str, Any] = {
        "googleVolumeId": first.get("id"),
        "googleVolumeInfo": volume_info,
        "title": str(title) if title is not None else None,
        "authors": authors,
        "publishedDate": volume_info.get("publishedDate"),
        "pageCount": volume_info.get("pageCount"),
        "categories": categories,
        "thumbnail": thumbnail,
    }
    return out

