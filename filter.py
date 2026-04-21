"""Dedupe against seen-state, score items by researcher signal, return ranked digest."""
from __future__ import annotations
import json
from datetime import date, datetime, timedelta
from pathlib import Path

SEEN_PATH = Path(__file__).parent / "seen.json"
SEEN_RETENTION_DAYS = 21

# Keyword filter: broad whitelist for "LLM-enhancing" topic relevance.
TOPIC_WHITELIST = [
    "llm", "language model", "agent", "agentic", "rag", "retrieval",
    "fine-tun", "lora", "qlora", "abliter", "uncensor", "jailbreak",
    "mcp", "model context protocol", "tool use", "tool-use", "function call",
    "inference", "vllm", "sglang", "llama.cpp", "ollama", "mlx",
    "embedding", "vector", "memory", "long-context", "context window",
    "reasoning", "chain of thought", "cot", "react",
    "diffusion", "multimodal", "vision-language", "vlm",
    "evaluation", "benchmark", "eval ", "leaderboard",
    "deepseek", "qwen", "llama", "mistral", "gemma", "claude", "gpt",
    "anthropic", "openai", "huggingface", "hugging face",
    "transformer", "attention", "moe", "mixture of experts",
    "agent framework", "multi-agent", "swarm", "autonomous",
    "mirofish", "letta", "memgpt", "browser-use", "browseruse",
]

LOW_QUALITY_KEYWORDS = [
    "no-code", "no code", "drag and drop", "drag-and-drop",
    "best chatgpt prompts", "course on udemy", "ai newsletter",
    "[hiring]", "looking for", "side hustle",
]

RESEARCHER_BONUS_KEYWORDS = [
    "abliter", "uncensor", "jailbreak", "self-hosted", "local-first",
    "open weights", "open-source", "from scratch", "pure pytorch",
    "novel architecture", "research", "paper",
]


def _topic_relevant(item: dict) -> bool:
    text = f"{item.get('title','')} {item.get('description','')}".lower()
    if any(b in text for b in LOW_QUALITY_KEYWORDS):
        return False
    # arXiv/HF papers always pass - they're already keyword-filtered upstream
    if item["source"] == "arxiv":
        return True
    if item["source"] == "huggingface" and item["extra"].get("kind") == "paper":
        return True
    # Everything else needs at least one whitelist hit
    return any(k in text for k in TOPIC_WHITELIST)


def _base_score(item: dict) -> float:
    src = item["source"]
    if src == "github":
        spd = item["extra"].get("stars_per_day", 0) or 0
        return min(100.0, spd * 2)
    if src == "hn":
        pts = item["score"]
        cmts = item["extra"].get("comments", 0)
        return min(100.0, pts / 2.0 + cmts / 4.0)
    if src == "reddit":
        ups = item["score"]
        cmts = item["extra"].get("comments", 0)
        return min(100.0, ups / 10.0 + cmts / 5.0)
    if src == "huggingface":
        if item["extra"].get("kind") == "model":
            ts = item["extra"].get("trending_score") or 0
            return min(100.0, ts * 5.0)
        return min(100.0, item["score"] * 5.0)  # paper upvotes
    if src == "arxiv":
        return 30.0
    return 0.0


def _signal_adjustments(item: dict, multi_source_count: int) -> float:
    text = f"{item.get('title','')} {item.get('description','')}".lower()
    bonus = sum(7 for k in RESEARCHER_BONUS_KEYWORDS if k in text)
    multi_bonus = (multi_source_count - 1) * 25  # appearing in 2+ sources is huge signal
    return bonus + multi_bonus


def _multi_source_count(item: dict, all_items: list[dict]) -> int:
    title_lc = item.get("title", "").lower().strip()
    if not title_lc:
        return 1
    count = 0
    seen_sources = set()
    for other in all_items:
        if other.get("title", "").lower().strip() == title_lc:
            seen_sources.add(other["source"])
    return max(1, len(seen_sources))


def load_seen() -> dict:
    if not SEEN_PATH.exists():
        return {}
    try:
        return json.loads(SEEN_PATH.read_text())
    except json.JSONDecodeError:
        return {}


def save_seen(seen: dict) -> None:
    cutoff = (date.today() - timedelta(days=SEEN_RETENTION_DAYS)).isoformat()
    pruned = {k: v for k, v in seen.items() if v >= cutoff}
    SEEN_PATH.write_text(json.dumps(pruned, indent=2, sort_keys=True))


def _key(item: dict) -> str:
    return f"{item['source']}:{item['id']}"


def rank_and_filter(items: list[dict], today: str | None = None) -> dict:
    """
    Returns:
        {
            "all_new": list of new (unseen, topic-relevant) items, with 'score' added,
            "daily_top": top 5 by score,
            "weekly_top": top 7 (filled by main.py on Sundays from a wider window)
        }
    """
    today = today or date.today().isoformat()
    seen = load_seen()

    relevant = [i for i in items if _topic_relevant(i)]

    new_items = []
    for item in relevant:
        k = _key(item)
        if k in seen:
            continue
        msc = _multi_source_count(item, relevant)
        item["score_total"] = round(_base_score(item) + _signal_adjustments(item, msc), 1)
        item["multi_source_count"] = msc
        new_items.append(item)

    new_items.sort(key=lambda x: x["score_total"], reverse=True)

    # Mark them seen now (we'll save after the email actually sends)
    for item in new_items:
        seen[_key(item)] = today

    return {
        "all_new": new_items,
        "daily_top": new_items[:5],
        "seen_state": seen,
    }
