# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt
playwright install chromium

# Run the full pipeline (scrape → rank → report)
python main.py

# Skip scraping and use existing data/raw/*.json
python main.py --skip-scrape

# Run all tests
pytest

# Run a single test file or test
pytest tests/test_tools.py
pytest tests/test_tools.py::test_score_listing_cebu_scores_higher_than_manila
```

Environment: requires a `.env` file with `GROQ_API_KEY`.

## Architecture

The pipeline runs in three stages, wired together in `main.py`:

1. **Scrape** — `scrapers/prosple.py` launches a headless Chromium browser via Playwright, extracts the `apolloState` JSON embedded in the page's `__NEXT_DATA__` script tag, and normalises each `Opportunity:*` entry into a flat dict. Output goes to `data/raw/prosple.json`. The `description` field is often empty because it comes from `overview.summary`, which is only populated on individual listing pages — not the list page.

2. **Agent loop** — `agent/agent.py` runs a tool-calling loop against Groq's `llama-3.3-70b-versatile`. The LLM is given only title/company/deadline summaries (not full listing dicts) and orchestrates calls to five tools in a fixed order: `filter_expired → score_listing → deduplicate → rank_listings → write_report`. The actual listing state lives in Python (`current`), not in the LLM context — tool calls always operate on the full current list regardless of what arguments the LLM passes.

3. **Tools** — `agent/tools.py` contains all pure-Python processing. Scoring is heuristic: location (Cebu = 25pts, remote = 20pts), skill keyword matches against description+requirements (8pts each, max 40pts), internship title keywords (15pts), paid compensation (10pts), known deadline (10pts), capped at 100.

### Adding a new scraper

1. Create `scrapers/<source>.py` with a `scrape() -> list[dict]` function returning the standard listing schema (same keys as prosple).
2. Register it in `main.py`'s `run_scrapers()` dict.
3. Add the source name to `tool_fns.deduplicate`'s `source_priority` in `agent/tools.py`.

### Listing schema

```python
{
    "title": str,
    "company": str,
    "location": str,
    "deadline": "YYYY-MM-DD" | None,
    "compensation": str | None,
    "description": str,       # often empty — fetched from list page only
    "requirements": [str],    # study field labels (e.g. "IT & Computer Science")
    "source": str,            # scraper name
    "url": str,
}
```
