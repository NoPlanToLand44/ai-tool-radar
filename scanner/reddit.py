"""Reddit source: r/LocalLLaMA + r/MachineLearning top posts (no auth needed)."""
from __future__ import annotations
import requests

UA = "ai-tool-radar/0.1 (by u/NoPlanToLand44)"
SUBS = ["LocalLLaMA", "MachineLearning"]


def scan_reddit(window: str = "day", per_sub: int = 25) -> list[dict]:
    """window: 'day' for daily digest, 'week' for weekly roundup."""
    seen: dict[str, dict] = {}
    for sub in SUBS:
        url = f"https://www.reddit.com/r/{sub}/top.json"
        params = {"t": window, "limit": per_sub}
        try:
            r = requests.get(url, params=params, headers={"User-Agent": UA}, timeout=20)
            r.raise_for_status()
            for child in r.json().get("data", {}).get("children", []):
                d = child["data"]
                if d.get("stickied"):
                    continue
                ups = d.get("ups", 0)
                if ups < 50:
                    continue
                pid = d["id"]
                seen[pid] = {
                    "source": "reddit",
                    "id": f"{sub}/{pid}",
                    "title": d.get("title", ""),
                    "url": d.get("url_overridden_by_dest") or f"https://reddit.com{d.get('permalink','')}",
                    "description": (d.get("selftext") or "")[:400],
                    "score": ups,
                    "extra": {
                        "subreddit": sub,
                        "comments": d.get("num_comments", 0),
                        "upvote_ratio": d.get("upvote_ratio"),
                        "permalink": f"https://reddit.com{d.get('permalink','')}",
                        "flair": d.get("link_flair_text"),
                    },
                }
        except requests.RequestException as e:
            print(f"[reddit] r/{sub} failed: {e}")
            continue

    return list(seen.values())
