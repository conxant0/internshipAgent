# Internship Agent — Design Spec
**Date:** 2026-04-16
**Status:** Approved

---

## Overview

An AI agent that replaces the manual process of checking multiple job boards daily. Scrapers collect raw internship listings from Philippine job boards, an agentic loop scores and ranks them against a CS student profile, and a clean markdown report is written as output.

**Built as a portfolio project** targeting the AI Engineer Intern role at Foundry for Good (Fuller Focus). The project demonstrates end-to-end delivery of a system that replaces manual research work — directly mirroring the role's core expectation.

**Student profile the agent scores against:**
- 3rd year CS student, based in Cebu
- Skills: Python, Django, React, AWS, Docker

---

## Architecture

Three independent layers communicating through flat files:

```
┌─────────────────────────────────────────┐
│              Entry Point                │
│              main.py                    │
└──────────────────┬──────────────────────┘
                   │
       ┌───────────▼───────────┐
       │     Scraper Layer     │
       │  prosple.py           │
       │  kalibrr.py           │
       │  jobstreet.py         │
       └───────────┬───────────┘
                   │ raw JSON files
                   │ (data/raw/*.json)
       ┌───────────▼───────────┐
       │     Agent Layer       │
       │  agent.py             │◄──── tools.py
       │  llm_client.py        │◄──── groq / swappable
       └───────────┬───────────┘
                   │
       ┌───────────▼───────────┐
       │     Output Layer      │
       │  output/report.md     │
       └───────────────────────┘
```

**Isolation rule:** `scrapers/` never imports from `agent/`, and `agent/` never imports from `scrapers/`. They communicate only through JSON files in `data/raw/`. This makes each layer independently debuggable.

---

## Project Structure

```
internshipAgent/
├── main.py                  # entry point, --skip-scrape flag
├── requirements.txt
├── .env                     # GROQ_API_KEY lives here
│
├── scrapers/
│   ├── __init__.py
│   ├── prosple.py           # MVP source
│   ├── kalibrr.py           # post-MVP
│   └── jobstreet.py         # post-MVP
│
├── agent/
│   ├── __init__.py
│   ├── agent.py             # agentic loop
│   ├── llm_client.py        # thin Groq wrapper (swappable)
│   └── tools.py             # all tool definitions
│
├── data/
│   └── raw/                 # prosple.json (MVP), kalibrr.json, jobstreet.json (post-MVP)
│
└── output/
    └── report.md            # final ranked report
```

---

## Data Schema

Every scraper outputs a list of listings in this exact shape. Missing fields are `null`, never omitted.

```json
{
  "title": "Software Engineering Intern",
  "company": "Acme Corp",
  "location": "Cebu / Remote",
  "deadline": "2026-05-01",
  "compensation": "Paid / 5000 per month",
  "description": "...",
  "requirements": ["Python", "Django"],
  "source": "internph",
  "url": "https://..."
}
```

---

## Scraper Layer

Three scrapers, one per source. All use Playwright (headless Chromium) to handle bot protection and JS rendering.

| Scraper | Source | Status | Notes |
|---|---|---|---|
| `prosple.py` | ph.prosple.com | **MVP** | Next.js SSR — extract `__NEXT_DATA__` JSON from page source |
| `kalibrr.py` | kalibrr.com | Post-MVP | JS-rendered, needs Playwright |
| `jobstreet.py` | ph.jobstreet.com | Post-MVP | JS-rendered, needs Playwright |

**Why Playwright for all scrapers:** All viable PH job boards either use JavaScript rendering or have bot protection (AWS WAF, Cloudflare) that blocks plain `requests`. Playwright runs a real headless browser, passes bot challenges, and executes JavaScript — exactly what a real user's browser does. This is the industry-standard approach for production-grade scraping.

**Prosple scraping approach:** Playwright loads the page, bot challenge resolves, then we extract the `__NEXT_DATA__` script tag and parse it as JSON. The listings live at a known path inside that JSON (confirmed via browser inspection).

Each scraper is wrapped in error handling. A scraper that fails logs a warning and returns an empty list — it never crashes the full run. The agent proceeds with whatever data it has.

---

## Agent Layer

### LLM Client (`llm_client.py`)

A thin wrapper around the Groq API. This is the **only file that knows about Groq**. To switch to Anthropic or OpenAI, only this file changes.

- Model: `llama-3.3-70b-versatile` (Groq free tier)
- API key loaded from `.env`

### Agentic Loop (`agent.py`)

The agent receives:
- All raw listings from `data/raw/*.json`
- A system prompt describing the student profile
- The full tool definitions

It enters a loop, deciding which tools to call and in what order. The loop ends when the agent calls `write_report`.

### Tools (`tools.py`)

| Tool | Type | What it does |
|---|---|---|
| `filter_expired` | Hard filter | Drops listings where deadline has passed. Listings with `null` deadline are kept and passed through to scoring. |
| `score_listing` | Soft score | Scores a listing 0–100 across: location (Cebu/remote preferred), skills match (Python/Django/React/AWS/Docker), internship type (OJT/intern label preferred), compensation (paid preferred), deadline proximity (null deadline scores lower than a known future deadline) |
| `deduplicate` | Merge | Detects duplicates by fuzzy match on company name + title keywords. Keeps the version with the most non-null fields; uses longest description as tiebreaker. Source priority if still tied: Prosple > Kalibrr > JobStreet |
| `rank_listings` | Sort | Sorts final scored list descending by score |
| `write_report` | Output | Signals loop end, triggers report generation |

---

## Output

`output/report.md` — a ranked markdown file. Each entry:

```
## #1 — Software Engineering Intern @ Acme Corp
Score: 87/100 | Location: Cebu | Deadline: May 1, 2026 | Compensation: Paid
Skills matched: Python, Django

Short description of the role...

[View listing →](https://...)
```

---

## Error Handling

- **Scraper failure:** Caught per-scraper, logged as warning, returns empty list. Run continues.
- **Agent/API failure:** Raw JSON files remain on disk. Re-run with `--skip-scrape` to retry only the agent.
- **Expired listings:** Hard-filtered before scoring. Never appear in the report.
- **Null deadline:** Listing is kept but treated as lower priority in scoring.

---

## Entry Point & Scheduling

`main.py` supports a `--skip-scrape` flag:

```bash
# Full run (scrape + agent + report)
python main.py

# Agent-only re-run using existing raw data
python main.py --skip-scrape

# Future cron job (no restructuring needed)
0 8 * * * python main.py
```

---

## Tech Stack

| Component | Technology |
|---|---|
| Language | Python 3.11+ |
| Scraping | Playwright (headless Chromium) + BeautifulSoup for HTML parsing |
| LLM / Agent | Groq API, Llama 3.3 70B |
| Output | Markdown file |
| Config | python-dotenv |

---

## Key Design Decisions

1. **Flat JSON over SQLite** — 20–30 listings don't need a database. JSON files are easier to inspect and debug. SQLite is a natural upgrade path if scheduling and "new since last run" tracking are added later.

5. **Playwright over requests** — Every viable PH job board has bot protection (AWS WAF, Cloudflare) or JS rendering. Plain `requests` returns empty pages or challenge pages. Playwright runs a real headless browser, making it the only reliable approach. It also demonstrates production-grade scraping knowledge relevant to the target role.

2. **Swappable LLM client** — `llm_client.py` is the only file that touches the Groq SDK. Switching providers is a two-line change.

3. **Agent decides tool order** — the agent is not a fixed pipeline. It decides when to call each tool based on what it observes. This is what makes it an agent, not a script.

4. **Scrapers fail silently** — a broken scraper should never block the report. Partial data is more useful than no data.
