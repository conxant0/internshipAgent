# AGENTS.md

## Setup

```bash
pip install -r requirements.txt
playwright install chromium  # separate from pip install
```

Requires `.env` file with `GROQ_API_KEY` environment variable.

## Commands

```bash
python main.py              # full pipeline: scrape → rank → report
python main.py --skip-scrape  # use existing data/raw/*.json (faster for development)
pytest                       # run all tests
pytest tests/test_tools.py::test_name  # run single test
```

## Architecture

Pipeline runs in 3 stages via `main.py`:

1. **Scrape** (`scrapers/prosple.py`) — Uses Playwright headless browser to extract `apolloState` JSON from `__NEXT_DATA__` script tag. Output: `data/raw/prosple.json`. Note: `description` field is often empty because it comes from `overview.summary` which is only on individual listing pages.

2. **Agent loop** (`agent/agent.py`) — Tool-calling loop against Groq `llama-3.3-70b-versatile`. Five tools called in **fixed order**: `filter_expired → score_listing → deduplicate → rank_listings → write_report`. State lives in Python `current`, not LLM context — tools operate on full list regardless of args.

3. **Tools** (`agent/tools.py`) — Scoring heuristic:
   - Location: Cebu = 25pts, remote = 20pts
   - Skill keywords: 8pts each, max 40pts
   - Title keywords: 15pts
   - Paid compensation: 10pts
   - Known deadline: 10pts
   - Cap: 100pts

## Adding a new scraper

1. Create `scrapers/<source>.py` with `scrape() -> list[dict]` returning standard listing schema
2. Register in `main.py`'s `run_scrapers()` dict
3. Add source name to `tool_fns.deduplicate`'s `source_priority` in `agent/tools.py`

## Listing schema

| Field | Type | Notes |
|-------|------|-------|
| `title` | str | |
| `company` | str | |
| `location` | str | |
| `deadline` | str \| None | Format: YYYY-MM-DD |
| `compensation` | str \| None | |
| `description` | str | Often empty from list pages |
| `requirements` | [str] | Technical tools/skills only |
| `source` | str | Scraper name |
| `url` | str | |
| `summary` | str \| None | LLM-enriched (1-2 sentences) |
| `eligibility` | [str] \| None | LLM-enriched (year level, hours, degree restrictions) |

## Key files

- `main.py` — pipeline entrypoint, orchestrates scrapers and agent
- `agent/agent.py` — LLM tool-calling loop
- `agent/tools.py` — pure-Python processing (filter, score, deduplicate, rank, write_report)
- `agent/llm_client.py` — Groq API wrapper
- `scrapers/prosple.py` — current scraper implementation