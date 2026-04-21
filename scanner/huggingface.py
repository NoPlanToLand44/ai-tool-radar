"""HuggingFace source: trending models + daily papers."""
from __future__ import annotations
from datetime import date
import requests

MODELS_API = "https://huggingface.co/api/models"
PAPERS_API = "https://huggingface.co/api/daily_papers"


def scan_huggingface(per_endpoint: int = 25) -> list[dict]:
    items: list[dict] = []

    # Trending models
    try:
        r = requests.get(
            MODELS_API,
            params={"sort": "trendingScore", "direction": -1, "limit": per_endpoint, "full": "true"},
            timeout=20,
        )
        r.raise_for_status()
        for m in r.json():
            mid = m.get("id") or m.get("modelId")
            if not mid:
                continue
            items.append({
                "source": "huggingface",
                "id": f"model:{mid}",
                "title": mid,
                "url": f"https://huggingface.co/{mid}",
                "description": (m.get("pipeline_tag") or ""),
                "score": int(m.get("likes") or 0),
                "extra": {
                    "kind": "model",
                    "downloads": m.get("downloads", 0),
                    "trending_score": m.get("trendingScore"),
                    "tags": m.get("tags", []),
                    "lastModified": m.get("lastModified"),
                },
            })
    except requests.RequestException as e:
        print(f"[hf] models failed: {e}")

    # Daily papers
    try:
        r = requests.get(PAPERS_API, params={"date": date.today().isoformat()}, timeout=20)
        if r.status_code == 200:
            for p in r.json()[:per_endpoint]:
                paper = p.get("paper", {})
                pid = paper.get("id")
                if not pid:
                    continue
                items.append({
                    "source": "huggingface",
                    "id": f"paper:{pid}",
                    "title": paper.get("title", "").strip(),
                    "url": f"https://huggingface.co/papers/{pid}",
                    "description": (paper.get("summary") or "").strip()[:500],
                    "score": int(paper.get("upvotes") or 0),
                    "extra": {
                        "kind": "paper",
                        "arxiv_id": pid,
                        "num_comments": paper.get("numComments", 0),
                    },
                })
    except requests.RequestException as e:
        print(f"[hf] papers failed: {e}")

    return items
