"""arXiv source: recent cs.AI / cs.CL submissions matching LLM-tooling keywords."""
from __future__ import annotations
import feedparser
import urllib.parse

API = "http://export.arxiv.org/api/query"

KEYWORDS = [
    "agent", "tool use", "abliter", "uncensor", "fine-tun",
    "reasoning", "long-context", "memory", "rag", "retrieval",
    "alignment", "jailbreak", "safety", "inference", "speculative",
    "mixture of experts", "instruction tuning",
]


def _matches(text: str) -> bool:
    t = text.lower()
    return any(k in t for k in KEYWORDS)


def scan_arxiv(max_results: int = 60) -> list[dict]:
    query = "cat:cs.AI OR cat:cs.CL OR cat:cs.LG"
    params = {
        "search_query": query,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
        "max_results": max_results,
    }
    url = f"{API}?{urllib.parse.urlencode(params)}"
    items: list[dict] = []
    try:
        feed = feedparser.parse(url)
        for e in feed.entries:
            text = f"{e.title} {e.summary}"
            if not _matches(text):
                continue
            arxiv_id = e.id.rsplit("/", 1)[-1]
            items.append({
                "source": "arxiv",
                "id": arxiv_id,
                "title": e.title.strip().replace("\n", " "),
                "url": e.link,
                "description": e.summary.strip().replace("\n", " ")[:500],
                "score": 0,  # arxiv has no score; ranked by recency only
                "extra": {
                    "authors": [a.get("name") for a in e.get("authors", [])],
                    "published": e.get("published"),
                    "categories": [t.term for t in e.get("tags", [])],
                },
            })
    except Exception as ex:
        print(f"[arxiv] failed: {ex}")
    return items
