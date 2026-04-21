"""GitHub source: newish high-velocity repos in LLM-tooling space."""
from __future__ import annotations
import os
from datetime import datetime, timedelta, timezone
import requests

API = "https://api.github.com/search/repositories"

QUERIES = [
    "topic:llm",
    "topic:agent",
    "topic:rag",
    "topic:fine-tuning",
    "topic:abliteration",
    "topic:mcp",
    "topic:llm-agent",
    "topic:multi-agent",
    "topic:llm-inference",
]


def _headers() -> dict:
    h = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    tok = os.environ.get("GITHUB_TOKEN")
    if tok:
        h["Authorization"] = f"Bearer {tok}"
    return h


def _stars_per_day(stars: int, created_at: str) -> float:
    created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    age_days = max(1.0, (datetime.now(timezone.utc) - created).total_seconds() / 86400)
    return stars / age_days


def scan_github(days: int = 60, per_query: int = 15) -> list[dict]:
    """Return high-velocity repos created in the last `days` days, deduped."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    seen: dict[str, dict] = {}

    for q in QUERIES:
        params = {
            "q": f"{q} created:>{cutoff}",
            "sort": "stars",
            "order": "desc",
            "per_page": per_query,
        }
        try:
            r = requests.get(API, headers=_headers(), params=params, timeout=20)
            r.raise_for_status()
            for item in r.json().get("items", []):
                full = item["full_name"]
                if full in seen:
                    continue
                seen[full] = {
                    "source": "github",
                    "id": full,
                    "title": full,
                    "url": item["html_url"],
                    "description": (item.get("description") or "").strip(),
                    "score": item["stargazers_count"],
                    "extra": {
                        "stars_per_day": round(
                            _stars_per_day(item["stargazers_count"], item["created_at"]), 1
                        ),
                        "language": item.get("language"),
                        "topics": item.get("topics", []),
                        "created_at": item["created_at"],
                        "pushed_at": item["pushed_at"],
                    },
                }
        except requests.RequestException as e:
            print(f"[github] query {q!r} failed: {e}")
            continue

    return list(seen.values())
