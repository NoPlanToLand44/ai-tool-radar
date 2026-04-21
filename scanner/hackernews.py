"""Hacker News source via Algolia search API."""
from __future__ import annotations
import time
import requests

API = "https://hn.algolia.com/api/v1/search"

QUERIES = [
    "LLM agent",
    "LLM tool",
    "abliteration",
    "fine-tuning",
    "open source AI",
    "model context protocol",
    "uncensor",
    "agent framework",
    "multi-agent",
    "vLLM SGLang",
]


def scan_hn(window_hours: int = 36, per_query: int = 15) -> list[dict]:
    """HN stories in the last window_hours containing any query keyword."""
    cutoff = int(time.time()) - window_hours * 3600
    seen: dict[str, dict] = {}

    for q in QUERIES:
        params = {
            "query": q,
            "tags": "story",
            "numericFilters": f"created_at_i>{cutoff}",
            "hitsPerPage": per_query,
        }
        try:
            r = requests.get(API, params=params, timeout=20)
            r.raise_for_status()
            for hit in r.json().get("hits", []):
                obj_id = hit["objectID"]
                if obj_id in seen:
                    continue
                points = hit.get("points") or 0
                comments = hit.get("num_comments") or 0
                if points < 10:  # noise floor
                    continue
                url = hit.get("url") or f"https://news.ycombinator.com/item?id={obj_id}"
                seen[obj_id] = {
                    "source": "hn",
                    "id": obj_id,
                    "title": hit.get("title") or "",
                    "url": url,
                    "description": "",
                    "score": points,
                    "extra": {
                        "comments": comments,
                        "hn_url": f"https://news.ycombinator.com/item?id={obj_id}",
                        "author": hit.get("author"),
                        "created_at": hit.get("created_at"),
                    },
                }
        except requests.RequestException as e:
            print(f"[hn] query {q!r} failed: {e}")
            continue

    return list(seen.values())
