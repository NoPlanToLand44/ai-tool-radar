"""Render digest as HTML + plain text and send via Resend API."""
from __future__ import annotations
import html
import os
import re
import requests

RESEND_API = "https://api.resend.com/emails"
ARCHIVE_URL_TEMPLATE = "https://github.com/NoPlanToLand44/ai-tool-radar/blob/main/digests/{date}.md"

# Gmail's content filter scores these heavily for new senders. Sanitize email body only;
# the GitHub-archived markdown keeps the original wording.
_TRIGGER_PATTERNS = [
    (re.compile(r"\babliterat\w*\b", re.IGNORECASE), "directional-ablation"),
    (re.compile(r"\buncensor\w*\b", re.IGNORECASE), "unaligned"),
    (re.compile(r"\bdecensor\w*\b", re.IGNORECASE), "unaligned"),
    (re.compile(r"\bjailbr[eo]\w*\b", re.IGNORECASE), "safety-removed"),
]
# URLs must be preserved verbatim — replacing keywords inside them would 404 the link.
# Stop at whitespace, quotes, angle brackets, parens — i.e. typical URL boundaries in HTML/text.
_URL_RE = re.compile(r"""https?://[^\s"'<>()\]\[]+""", re.IGNORECASE)


def _sanitize(s: str) -> str:
    """Replace trigger keywords outside of URLs. URL substrings stay intact."""
    def _sub_keywords(chunk: str) -> str:
        for pat, repl in _TRIGGER_PATTERNS:
            chunk = pat.sub(repl, chunk)
        return chunk

    parts: list[str] = []
    cursor = 0
    for m in _URL_RE.finditer(s):
        parts.append(_sub_keywords(s[cursor:m.start()]))
        parts.append(m.group(0))  # URL preserved verbatim
        cursor = m.end()
    parts.append(_sub_keywords(s[cursor:]))
    return "".join(parts)


def _blurb_for(item_key: str, blurbs: list[dict]) -> str:
    for b in blurbs:
        if b.get("id") == item_key:
            return b.get("blurb", "")
    return ""


def _source_tag(src: str) -> str:
    return {
        "github": "GitHub",
        "hn": "HN",
        "reddit": "Reddit",
        "huggingface": "HF",
        "arxiv": "arXiv",
    }.get(src, src)


def _signal_metric(item: dict) -> str:
    src = item["source"]
    extra = item.get("extra", {}) or {}
    if src == "github":
        return f"{item['score']}★ ({extra.get('stars_per_day', 0)}/day)"
    if src == "hn":
        return f"{item['score']} pts · {extra.get('comments', 0)} comments"
    if src == "reddit":
        return f"r/{extra.get('subreddit')} · {item['score']} ups · {extra.get('comments', 0)} comments"
    if src == "huggingface":
        if extra.get("kind") == "model":
            return f"trending {extra.get('trending_score', 0)} · {extra.get('downloads', 0)} dl"
        return f"{item['score']} upvotes (paper)"
    if src == "arxiv":
        return "arXiv preprint"
    return ""


def render_text(digest: dict, today: str, mode: str) -> str:
    daily = digest["daily_top"]
    blurbs = digest["llm"].get("daily_blurbs", [])
    analysis = digest["llm"].get("daily_analysis", "")
    weekly_analysis = digest["llm"].get("weekly_analysis", "")
    weekly = digest.get("weekly_top", [])

    n_new = len(digest.get("all_new", []))
    multi = sum(1 for i in daily if i.get("multi_source_count", 1) > 1)

    lines = []
    lines.append(f"AI TOOL RADAR — {today}")
    lines.append(f"{n_new} new items today · {len(daily)} highlighted · {multi} cross-source")
    lines.append(f"Full archive: {ARCHIVE_URL_TEMPLATE.format(date=today)}")
    lines.append("")
    lines.append("=" * 60)
    lines.append("TODAY'S HIGHLIGHTS")
    lines.append("=" * 60)
    for i, item in enumerate(daily, 1):
        key = f"{item['source']}:{item['id']}"
        lines.append("")
        lines.append(f"{i}. [{_source_tag(item['source'])}] {item['title']}")
        lines.append(f"   {item['url']}")
        lines.append(f"   Signal: {_signal_metric(item)} · score {item.get('score_total','?')}")
        b = _blurb_for(key, blurbs)
        if b:
            lines.append(f"   → {b}")
    lines.append("")
    lines.append("=" * 60)
    lines.append("ANALYSIS")
    lines.append("=" * 60)
    lines.append(analysis or "(no analysis)")

    if mode == "sunday" and weekly:
        lines.append("")
        lines.append("=" * 60)
        lines.append("THIS WEEK")
        lines.append("=" * 60)
        for i, item in enumerate(weekly[:7], 1):
            lines.append(f"{i}. [{_source_tag(item['source'])}] {item['title']}")
            lines.append(f"   {item['url']}  ·  {_signal_metric(item)}")
        if weekly_analysis:
            lines.append("")
            lines.append("Weekly take:")
            lines.append(weekly_analysis)

    lines.append("")
    lines.append("--")
    lines.append("ai-tool-radar · digest archived in /digests/ · github.com/NoPlanToLand44/ai-tool-radar")
    return "\n".join(lines)


def render_html(digest: dict, today: str, mode: str) -> str:
    daily = digest["daily_top"]
    blurbs = digest["llm"].get("daily_blurbs", [])
    analysis = digest["llm"].get("daily_analysis", "")
    weekly_analysis = digest["llm"].get("weekly_analysis", "")
    weekly = digest.get("weekly_top", [])
    n_new = len(digest.get("all_new", []))
    multi = sum(1 for i in daily if i.get("multi_source_count", 1) > 1)

    def card(item: dict, idx: int) -> str:
        key = f"{item['source']}:{item['id']}"
        b = html.escape(_blurb_for(key, blurbs))
        title = html.escape(item["title"])
        url = html.escape(item["url"])
        src = _source_tag(item["source"])
        sig = html.escape(_signal_metric(item))
        score = item.get("score_total", "?")
        multi_badge = " 🔥" if item.get("multi_source_count", 1) > 1 else ""
        return f"""
        <div style="border-left:3px solid #4a90e2; padding:10px 14px; margin:14px 0; background:#1a1a1a;">
          <div style="font-size:12px; color:#888;">#{idx} · <b>{src}</b> · {sig} · score <b>{score}</b>{multi_badge}</div>
          <div style="font-size:16px; margin:4px 0 6px 0;"><a href="{url}" style="color:#7fb3ff; text-decoration:none;">{title}</a></div>
          {f'<div style="color:#ddd; font-size:14px;">{b}</div>' if b else ''}
        </div>
        """

    cards = "\n".join(card(item, i) for i, item in enumerate(daily, 1))

    weekly_html = ""
    if mode == "sunday" and weekly:
        rows = "\n".join(
            f'<li><b>{html.escape(_source_tag(it["source"]))}</b> · '
            f'<a href="{html.escape(it["url"])}" style="color:#7fb3ff;">{html.escape(it["title"])}</a> '
            f'<span style="color:#888;">— {html.escape(_signal_metric(it))}</span></li>'
            for it in weekly[:7]
        )
        weekly_take = f'<p style="color:#ddd;">{html.escape(weekly_analysis)}</p>' if weekly_analysis else ""
        weekly_html = f"""
        <h2 style="color:#4a90e2; border-bottom:1px solid #333; padding-bottom:4px;">This Week</h2>
        <ol style="line-height:1.7;">{rows}</ol>
        {weekly_take}
        """

    return f"""<!doctype html>
<html><body style="background:#0d0d0d; color:#e0e0e0; font-family:-apple-system,Segoe UI,Roboto,sans-serif; max-width:680px; margin:0 auto; padding:24px;">
  <div style="font-size:13px; color:#888;">AI TOOL RADAR · {html.escape(today)}</div>
  <div style="font-size:13px; color:#888;">{n_new} new items · {len(daily)} highlighted · {multi} cross-source</div>
  <div style="font-size:12px; margin-bottom:18px;"><a href="{ARCHIVE_URL_TEMPLATE.format(date=today)}" style="color:#7fb3ff;">→ full archive on github</a></div>

  <h2 style="color:#4a90e2; border-bottom:1px solid #333; padding-bottom:4px;">Today's Highlights</h2>
  {cards}

  <h2 style="color:#4a90e2; border-bottom:1px solid #333; padding-bottom:4px;">Analysis</h2>
  <p style="color:#ddd; line-height:1.5;">{html.escape(analysis or '(no analysis)')}</p>

  {weekly_html}

  <hr style="border:none; border-top:1px solid #222; margin:28px 0 12px 0;">
  <div style="font-size:11px; color:#666;">ai-tool-radar · daily digest · sources: GitHub trending, HN, r/LocalLLaMA, HuggingFace, arXiv</div>
</body></html>
"""


def send_email(digest: dict, today: str, mode: str) -> dict:
    api_key = os.environ.get("RESEND_API_KEY")
    to_addr = os.environ.get("DIGEST_TO", "emil.shupev@gmail.com")
    from_addr = os.environ.get("DIGEST_FROM", "AI Tool Radar <onboarding@resend.dev>")
    if not api_key:
        raise RuntimeError("RESEND_API_KEY not set")

    n_new = len(digest.get("all_new", []))
    multi = sum(1 for i in digest["daily_top"] if i.get("multi_source_count", 1) > 1)
    flag = " 🔥" if multi > 0 else ""
    subject = f"AI Tools Digest — {today} ({n_new} new, {multi} cross-source){flag}"
    if mode == "sunday":
        subject = f"AI Tools — Weekly Digest — {today}"

    payload = {
        "from": from_addr,
        "to": [to_addr],
        "subject": _sanitize(subject),
        "html": _sanitize(render_html(digest, today, mode)),
        "text": _sanitize(render_text(digest, today, mode)),
    }
    r = requests.post(
        RESEND_API,
        json=payload,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        timeout=20,
    )
    r.raise_for_status()
    return r.json()
