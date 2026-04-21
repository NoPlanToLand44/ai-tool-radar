"""ai-tool-radar entry point. Run daily via GitHub Actions (or `python main.py` locally)."""
from __future__ import annotations
import os
import sys
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime
from pathlib import Path

from scanner import scan_github, scan_hn, scan_reddit, scan_huggingface, scan_arxiv
from filter import rank_and_filter, save_seen, _topic_relevant, _base_score, _signal_adjustments, _multi_source_count
from summarize import summarize
from email_send import send_email, render_text

DIGESTS_DIR = Path(__file__).parent / "digests"


def run_scanners(mode: str) -> tuple[list[dict], list[dict]]:
    """Returns (items_for_daily, items_for_weekly_or_empty)."""
    daily_jobs = {
        "github": lambda: scan_github(days=60),
        "hn": lambda: scan_hn(window_hours=36),
        "reddit_day": lambda: scan_reddit(window="day"),
        "huggingface": lambda: scan_huggingface(),
        "arxiv": lambda: scan_arxiv(),
    }
    weekly_jobs = {"reddit_week": lambda: scan_reddit(window="week")} if mode == "sunday" else {}

    items: list[dict] = []
    weekly_items: list[dict] = []

    with ThreadPoolExecutor(max_workers=6) as ex:
        futs = {ex.submit(fn): name for name, fn in {**daily_jobs, **weekly_jobs}.items()}
        for fut in as_completed(futs):
            name = futs[fut]
            try:
                got = fut.result()
                print(f"[scan] {name}: {len(got)} items")
                if name == "reddit_week":
                    weekly_items.extend(got)
                else:
                    items.extend(got)
            except Exception as e:
                print(f"[scan] {name} FAILED: {e}")

    return items, weekly_items


def build_weekly_top(weekly_items: list[dict], already_in_daily: list[dict]) -> list[dict]:
    """Independent ranking for the weekly section. No dedupe against seen.json — week is a roundup."""
    daily_keys = {f"{i['source']}:{i['id']}" for i in already_in_daily}
    relevant = [i for i in weekly_items if _topic_relevant(i)]
    scored = []
    for item in relevant:
        if f"{item['source']}:{item['id']}" in daily_keys:
            continue
        msc = _multi_source_count(item, relevant)
        item["score_total"] = round(_base_score(item) + _signal_adjustments(item, msc), 1)
        item["multi_source_count"] = msc
        scored.append(item)
    scored.sort(key=lambda x: x["score_total"], reverse=True)
    return scored[:7]


def archive_digest(today: str, digest: dict, mode: str) -> None:
    DIGESTS_DIR.mkdir(exist_ok=True)
    md = f"# {today} ({mode})\n\n```\n{render_text(digest, today, mode)}\n```\n"
    (DIGESTS_DIR / f"{today}.md").write_text(md)


def main() -> int:
    today = date.today().isoformat()
    weekday = datetime.now().weekday()  # Monday=0 .. Sunday=6
    mode = "sunday" if weekday == 6 else "daily"
    print(f"[main] {today} mode={mode}")

    raw_items, weekly_raw = run_scanners(mode)
    print(f"[main] total raw items: {len(raw_items)}  weekly_raw: {len(weekly_raw)}")

    ranked = rank_and_filter(raw_items, today=today)
    print(f"[main] new (post-dedupe + filter): {len(ranked['all_new'])}, daily_top: {len(ranked['daily_top'])}")

    weekly_top = build_weekly_top(weekly_raw, ranked["daily_top"]) if mode == "sunday" else []

    # Empty digest? Send a one-liner so you know the system is alive.
    if not ranked["daily_top"]:
        print("[main] no new items — sending heartbeat-only digest")
        ranked["daily_top"] = []
        llm = {
            "daily_blurbs": [],
            "daily_analysis": "Slow news day. No new items crossed the topic + signal filter.",
            "weekly_analysis": "",
        }
    else:
        try:
            llm = summarize(ranked["daily_top"], weekly_top, today, mode)
        except Exception as e:
            print(f"[main] summarize FAILED: {e}")
            traceback.print_exc()
            llm = {
                "daily_blurbs": [],
                "daily_analysis": f"(LLM summary failed: {e})",
                "weekly_analysis": "",
            }

    digest = {
        "all_new": ranked["all_new"],
        "daily_top": ranked["daily_top"],
        "weekly_top": weekly_top,
        "llm": llm,
    }

    if os.environ.get("DRY_RUN") == "1":
        print("[main] DRY_RUN=1 — printing digest, not sending email")
        print(render_text(digest, today, mode))
        return 0

    try:
        result = send_email(digest, today, mode)
        print(f"[main] email sent: {result}")
    except Exception as e:
        print(f"[main] email FAILED: {e}")
        traceback.print_exc()
        return 1

    save_seen(ranked["seen_state"])
    archive_digest(today, digest, mode)
    print(f"[main] done. archived to digests/{today}.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
