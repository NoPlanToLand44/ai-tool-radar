"""DeepSeek call: one-line blurbs per item + daily/weekly analysis paragraphs."""
from __future__ import annotations
import json
import os
from openai import OpenAI

DEEPSEEK_BASE = "https://api.deepseek.com"
MODEL = "deepseek-chat"

SYSTEM = """You are an analyst writing a daily AI-tools digest for a technical builder.
The reader cares about tools that ENHANCE LLM capabilities: agent frameworks, model
modification (abliteration, fine-tuning), inference runtimes, memory layers, browser
agents, MCP, novel research. They explicitly do NOT care about no-code wrappers,
generic chatbots, AI productivity SaaS, or VC-bait announcements.

Lead with substance. Be terse. No marketing speak. If something is overhyped or
half-baked, say so. The reader prefers a sharp negative take to a soft positive one.

Reader's existing toolkit: mirofish (multi-agent simulation), agency-agents,
heretic (abliteration). Tie new finds to that context when relevant.
"""

USER_TEMPLATE = """Date: {date}
Mode: {mode}

Today's top items (already scored and ranked):
{daily_json}
{weekly_block}

Return STRICT JSON with this shape (no prose around it, no code fence):
{{
  "daily_blurbs": [
    {{"id": "<source:id from input>", "blurb": "<1-2 sentences: what it is + why this reader would care or not. Be specific. Use 'Skip' or 'Worth a look' or 'Genuinely interesting' as needed.>"}}
  ],
  "daily_analysis": "<1 short paragraph (3-5 sentences). What pattern do you see in today's items? What's the takeaway? If today is a slow news day, say so.>",
  "weekly_analysis": "<1 paragraph IF mode=='sunday', else empty string. Pattern across the week's top items.>"
}}
"""


def _trim_item(item: dict) -> dict:
    """Send only the fields the model needs; saves tokens."""
    return {
        "id": f"{item['source']}:{item['id']}",
        "source": item["source"],
        "title": item["title"],
        "url": item["url"],
        "description": (item.get("description") or "")[:300],
        "score_total": item.get("score_total"),
        "multi_source_count": item.get("multi_source_count", 1),
        "extra": {
            k: v for k, v in (item.get("extra") or {}).items()
            if k in {"stars_per_day", "comments", "subreddit", "kind", "downloads", "trending_score", "topics"}
        },
    }


def summarize(daily_top: list[dict], weekly_top: list[dict] | None, today: str, mode: str) -> dict:
    """mode: 'daily' or 'sunday' (sunday includes a weekly section)."""
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY not set")

    client = OpenAI(api_key=api_key, base_url=DEEPSEEK_BASE)

    daily_json = json.dumps([_trim_item(i) for i in daily_top], indent=2)
    weekly_block = ""
    if mode == "sunday" and weekly_top:
        weekly_block = "\n\nThis week's top items (broader window):\n" + json.dumps(
            [_trim_item(i) for i in weekly_top], indent=2
        )

    prompt = USER_TEMPLATE.format(
        date=today, mode=mode, daily_json=daily_json, weekly_block=weekly_block
    )

    resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": prompt},
        ],
        temperature=0.4,
        response_format={"type": "json_object"},
        max_tokens=2000,
    )

    raw = resp.choices[0].message.content
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"[summarize] JSON parse failed: {e}\nRaw response:\n{raw}")
        return {
            "daily_blurbs": [],
            "daily_analysis": "(LLM returned invalid JSON — see logs)",
            "weekly_analysis": "",
        }
