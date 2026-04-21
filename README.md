# ai-tool-radar

Daily scanner that scrapes GitHub, HN, r/LocalLLaMA, HuggingFace, and arXiv for new
LLM-enhancing tools — agent frameworks, abliteration / fine-tuning, inference runtimes,
memory layers, MCP, browser agents, novel research — then sends a ranked digest email.

Built for builders who care about *researcher signal*, not no-code wrappers.

## Architecture

```
main.py
  ├─ scanner/          5 source modules (parallel, fail-isolated)
  │   ├─ github_trending.py
  │   ├─ hackernews.py
  │   ├─ reddit.py
  │   ├─ huggingface.py
  │   └─ arxiv_feed.py
  ├─ filter.py         topic whitelist + dedupe vs seen.json + scoring
  ├─ summarize.py      DeepSeek call → per-item blurbs + analysis paragraph
  └─ email_send.py     HTML + text render → Resend API
```

State: `seen.json` (21-day rolling dedupe) and `digests/YYYY-MM-DD.md` (archive).
Both committed back to the repo by the workflow.

## Schedule

GitHub Actions cron `0 6 * * *` UTC = 09:00 Sofia (DST) / 08:00 Sofia (winter).
Sundays include a weekly section. Manual run: Actions tab → "Daily AI Tools Digest" → Run workflow.

## Required secrets

| Secret | Where to get it |
|---|---|
| `RESEND_API_KEY` | resend.com → API Keys → Sending access |
| `DEEPSEEK_API_KEY` | platform.deepseek.com |

Optional repo variables: `DIGEST_TO`, `DIGEST_FROM`.

## Local testing

```bash
cd ai-tool-radar
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # fill in keys
set -a && source .env && set +a
DRY_RUN=1 python main.py   # print without sending
python main.py             # actually send the email
```

## Cost

- Resend: free tier (3000 emails/mo) — 30 emails/mo used
- DeepSeek: ~$0.005/day — ~$0.15/mo
- GitHub Actions: ~2 min/day — well inside free tier

## Tuning

- Add/remove keywords in `filter.py` → `TOPIC_WHITELIST`, `LOW_QUALITY_KEYWORDS`, `RESEARCHER_BONUS_KEYWORDS`
- Add subreddits in `scanner/reddit.py` → `SUBS`
- Add HN queries in `scanner/hackernews.py` → `QUERIES`
- Adjust scoring formula in `filter.py` → `_base_score`, `_signal_adjustments`
- The DeepSeek system prompt is in `summarize.py` → `SYSTEM` — edit to retune the analyst voice
