# Internship Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an AI agent that scrapes PH internship listings from Prosple, scores and ranks them against a CS student profile, and writes a clean markdown report.

**Architecture:** Scrapers fetch raw listings and write them to JSON files. A Groq-powered agent reads those files and enters a tool-use loop — deciding when to filter, score, deduplicate, rank, and write the report. The two layers communicate only through files, so each is independently debuggable.

**Tech Stack:** Python 3.11+, Playwright (headless Chromium), BeautifulSoup, Groq SDK (Llama 3.3 70B), python-dotenv, pytest

---

## File Map

| File | Responsibility |
|---|---|
| `main.py` | Entry point. Runs scrapers then agent. `--skip-scrape` flag. |
| `requirements.txt` | All dependencies |
| `.env` | `GROQ_API_KEY` (never committed) |
| `scrapers/__init__.py` | Empty |
| `scrapers/prosple.py` | Playwright scraper for ph.prosple.com |
| `agent/__init__.py` | Empty |
| `agent/tools.py` | All 5 tool functions: filter_expired, score_listing, deduplicate, rank_listings, write_report |
| `agent/llm_client.py` | Thin Groq wrapper. Only file that imports groq. |
| `agent/agent.py` | Agentic tool-use loop |
| `tests/test_tools.py` | Unit tests for all tool functions |
| `tests/test_agent.py` | Agent loop test with mocked LLM |
| `data/raw/` | Scraper output JSON files (gitignored) |
| `output/` | Report output (gitignored) |

---

## Task 1: Project Scaffold

**Files:**
- Create: `requirements.txt`
- Create: `.env.example`
- Create: `.gitignore`
- Create: `scrapers/__init__.py`
- Create: `agent/__init__.py`
- Create: `tests/__init__.py`
- Create: `data/raw/.gitkeep`
- Create: `output/.gitkeep`

- [ ] **Step 1: Create the folder structure**

Run these commands:
```bash
mkdir -p scrapers agent tests data/raw output
touch scrapers/__init__.py agent/__init__.py tests/__init__.py
touch data/raw/.gitkeep output/.gitkeep
```

- [ ] **Step 2: Create `requirements.txt`**

```
playwright==1.44.0
beautifulsoup4==4.12.3
groq==0.9.0
python-dotenv==1.0.1
pytest==8.2.0
```

- [ ] **Step 3: Create `.env.example`**

```
GROQ_API_KEY=your_key_here
```

- [ ] **Step 4: Create `.env` with your real key**

```bash
cp .env.example .env
# then open .env and paste your real GROQ_API_KEY
```

- [ ] **Step 5: Create `.gitignore`**

```
.env
data/raw/*.json
output/*.md
__pycache__/
*.pyc
.pytest_cache/
```

- [ ] **Step 6: Install dependencies**

```bash
pip install -r requirements.txt
playwright install chromium
```

Expected output from the playwright install: it downloads Chromium (~150MB). Takes 1-2 minutes.

- [ ] **Step 7: Verify Playwright works**

```bash
python3 -c "from playwright.sync_api import sync_playwright; print('Playwright OK')"
```

Expected: `Playwright OK`

- [ ] **Step 8: Commit**

```bash
git add requirements.txt .env.example .gitignore scrapers/__init__.py agent/__init__.py tests/__init__.py data/raw/.gitkeep output/.gitkeep
git commit -m "Set up project scaffold with folders, dependencies, and gitignore"
```

---

## Task 2: Agent Tools — Filtering and Scoring

**Files:**
- Create: `agent/tools.py`
- Create: `tests/test_tools.py`

These are pure Python functions with no external dependencies — easy to write, easy to test.

- [ ] **Step 1: Write the failing tests for `filter_expired` and `score_listing`**

Create `tests/test_tools.py`:

```python
import pytest
from agent.tools import filter_expired, score_listing

# ── Fixtures ─────────────────────────────────────────────────────────────────

FUTURE = "2099-12-31"
PAST   = "2000-01-01"

def make_listing(**kwargs):
    base = {
        "title": "Software Engineering Intern",
        "company": "Tech Corp",
        "location": "Cebu",
        "deadline": FUTURE,
        "compensation": "Paid",
        "description": "We use Python and Django for our backend.",
        "requirements": ["Python", "Django"],
        "source": "prosple",
        "url": "https://example.com/1",
    }
    base.update(kwargs)
    return base

# ── filter_expired ────────────────────────────────────────────────────────────

def test_filter_expired_removes_past_deadlines():
    listings = [
        make_listing(deadline=FUTURE),
        make_listing(deadline=PAST),
    ]
    result = filter_expired(listings)
    assert len(result) == 1
    assert result[0]["deadline"] == FUTURE

def test_filter_expired_keeps_null_deadline():
    listings = [make_listing(deadline=None)]
    result = filter_expired(listings)
    assert len(result) == 1

def test_filter_expired_empty_list():
    assert filter_expired([]) == []

# ── score_listing ─────────────────────────────────────────────────────────────

def test_score_listing_returns_int():
    listing = make_listing()
    scores = score_listing([listing])
    assert isinstance(scores[0]["score"], int)

def test_score_listing_cebu_scores_higher_than_manila():
    cebu   = make_listing(location="Cebu")
    manila = make_listing(location="Manila")
    cebu_score   = score_listing([cebu])[0]["score"]
    manila_score = score_listing([manila])[0]["score"]
    assert cebu_score > manila_score

def test_score_listing_skills_match_adds_points():
    with_skills    = make_listing(description="We use Python, Django, React, AWS, Docker")
    without_skills = make_listing(description="No relevant tech mentioned")
    high = score_listing([with_skills])[0]["score"]
    low  = score_listing([without_skills])[0]["score"]
    assert high > low

def test_score_listing_score_is_between_0_and_100():
    listing = make_listing()
    score = score_listing([listing])[0]["score"]
    assert 0 <= score <= 100
```

- [ ] **Step 2: Run the tests — they should all fail**

```bash
pytest tests/test_tools.py -v
```

Expected: `ImportError` — `agent.tools` doesn't exist yet.

- [ ] **Step 3: Create `agent/tools.py` with `filter_expired` and `score_listing`**

```python
from datetime import date
from typing import List


def filter_expired(listings: List[dict]) -> List[dict]:
    """Drop any listing whose deadline has already passed. Keep null deadlines."""
    today = date.today().isoformat()
    return [l for l in listings if l.get("deadline") is None or l["deadline"] >= today]


def score_listing(listings: List[dict]) -> List[dict]:
    """Add a 'score' field (0-100) to each listing. Returns a new list."""
    result = []
    for listing in listings:
        scored = dict(listing)
        scored["score"] = _compute_score(listing)
        result.append(scored)
    return result


def _compute_score(listing: dict) -> int:
    score = 0

    # Location — 25 pts
    location = (listing.get("location") or "").lower()
    if "cebu" in location:
        score += 25
    elif any(w in location for w in ["remote", "wfh", "work from home"]):
        score += 20

    # Skills match — 8 pts per skill, max 40
    skills = ["python", "django", "react", "aws", "docker"]
    text = (listing.get("description") or "").lower()
    text += " ".join(r.lower() for r in (listing.get("requirements") or []))
    matched = sum(1 for skill in skills if skill in text)
    score += matched * 8

    # Internship type — 15 pts
    title = (listing.get("title") or "").lower()
    if any(w in title for w in ["intern", "ojt", "trainee"]):
        score += 15

    # Compensation — 10 pts
    compensation = (listing.get("compensation") or "").lower()
    if compensation and "unpaid" not in compensation:
        score += 10

    # Known deadline — 10 pts (null deadline is penalised)
    if listing.get("deadline"):
        score += 10

    return min(score, 100)
```

- [ ] **Step 4: Run the tests — they should all pass**

```bash
pytest tests/test_tools.py -v
```

Expected: all 7 tests pass.

- [ ] **Step 5: Commit**

```bash
git add agent/tools.py tests/test_tools.py
git commit -m "Added filter_expired and score_listing tools with passing tests"
```

---

## Task 3: Agent Tools — Deduplication, Ranking, and Report

**Files:**
- Modify: `agent/tools.py`
- Modify: `tests/test_tools.py`

- [ ] **Step 1: Add tests for `deduplicate`, `rank_listings`, and `write_report` to `tests/test_tools.py`**

Append this to the bottom of `tests/test_tools.py`:

```python
from agent.tools import deduplicate, rank_listings, write_report
import os

# ── deduplicate ───────────────────────────────────────────────────────────────

def test_deduplicate_removes_exact_duplicate():
    a = make_listing(source="prosple")
    b = make_listing(source="kalibrr")  # same company+title, different source
    result = deduplicate([a, b])
    assert len(result) == 1

def test_deduplicate_keeps_richer_version():
    sparse = make_listing(description=None, compensation=None, source="kalibrr")
    rich   = make_listing(description="Full description here", compensation="Paid", source="prosple")
    result = deduplicate([sparse, rich])
    assert result[0]["description"] == "Full description here"

def test_deduplicate_keeps_different_companies():
    a = make_listing(company="Company A")
    b = make_listing(company="Company B")
    result = deduplicate([a, b])
    assert len(result) == 2

# ── rank_listings ─────────────────────────────────────────────────────────────

def test_rank_listings_sorted_descending():
    listings = [
        make_listing(score=40),
        make_listing(score=90),
        make_listing(score=60),
    ]
    result = rank_listings(listings)
    assert result[0]["score"] == 90
    assert result[1]["score"] == 60
    assert result[2]["score"] == 40

# ── write_report ──────────────────────────────────────────────────────────────

def test_write_report_creates_file(tmp_path):
    listings = [make_listing(score=85)]
    output_file = str(tmp_path / "report.md")
    path = write_report(listings, output_path=output_file)
    assert os.path.exists(path)

def test_write_report_contains_title(tmp_path):
    listings = [make_listing(title="Python Intern", score=85)]
    output_file = str(tmp_path / "report.md")
    write_report(listings, output_path=output_file)
    content = open(output_file).read()
    assert "Python Intern" in content

def test_write_report_contains_rank_number(tmp_path):
    listings = [make_listing(score=85)]
    output_file = str(tmp_path / "report.md")
    write_report(listings, output_path=output_file)
    content = open(output_file).read()
    assert "#1" in content
```

- [ ] **Step 2: Run the new tests — they should fail**

```bash
pytest tests/test_tools.py -v -k "deduplicate or rank or report"
```

Expected: `ImportError` — these functions don't exist yet.

- [ ] **Step 3: Add `deduplicate`, `rank_listings`, and `write_report` to `agent/tools.py`**

Append to the bottom of `agent/tools.py`:

```python
import os


def deduplicate(listings: List[dict]) -> List[dict]:
    """Merge duplicates across sources. Keeps the version with most non-null fields."""
    source_priority = {"prosple": 0, "kalibrr": 1, "jobstreet": 2}
    seen: dict = {}

    for listing in listings:
        company = (listing.get("company") or "").lower().strip()
        title_words = frozenset((listing.get("title") or "").lower().split())
        key = (company, title_words)

        if key not in seen:
            seen[key] = listing
        else:
            existing = seen[key]
            existing_score = sum(1 for v in existing.values() if v is not None)
            new_score = sum(1 for v in listing.values() if v is not None)

            if new_score > existing_score:
                seen[key] = listing
            elif new_score == existing_score:
                ep = source_priority.get(existing.get("source", ""), 99)
                np = source_priority.get(listing.get("source", ""), 99)
                if np < ep:
                    seen[key] = listing

    return list(seen.values())


def rank_listings(listings: List[dict]) -> List[dict]:
    """Sort listings by score descending."""
    return sorted(listings, key=lambda x: x.get("score", 0), reverse=True)


def write_report(listings: List[dict], output_path: str = "output/report.md") -> str:
    """Write the ranked report to a markdown file. Returns the file path."""
    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
    lines = ["# Internship Listings — Ranked Report\n"]

    for i, listing in enumerate(listings, 1):
        title        = listing.get("title") or "Untitled"
        company      = listing.get("company") or "Unknown"
        score        = listing.get("score", 0)
        location     = listing.get("location") or "Not specified"
        deadline     = listing.get("deadline") or "Not specified"
        compensation = listing.get("compensation") or "Not specified"
        description  = listing.get("description") or ""
        requirements = listing.get("requirements") or []
        url          = listing.get("url") or "#"

        lines.append(f"## #{i} — {title} @ {company}")
        lines.append(f"Score: {score}/100 | Location: {location} | Deadline: {deadline} | Compensation: {compensation}")
        if requirements:
            lines.append(f"Skills mentioned: {', '.join(requirements)}")
        lines.append("")
        if description:
            short = description[:300] + ("..." if len(description) > 300 else "")
            lines.append(short)
        lines.append("")
        lines.append(f"[View listing →]({url})")
        lines.append("")
        lines.append("---")
        lines.append("")

    content = "\n".join(lines)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)

    return output_path
```

- [ ] **Step 4: Run all tool tests**

```bash
pytest tests/test_tools.py -v
```

Expected: all 15 tests pass.

- [ ] **Step 5: Commit**

```bash
git add agent/tools.py tests/test_tools.py
git commit -m "Finished all 5 agent tools with full test coverage"
```

---

## Task 4: LLM Client

**Files:**
- Create: `agent/llm_client.py`

This is the only file that knows about Groq. To swap to Anthropic or OpenAI later, only this file changes.

- [ ] **Step 1: Create `agent/llm_client.py`**

```python
import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()


def chat(messages: list, tools: list = None):
    """
    Send messages to Groq and return the assistant message object.
    Pass tools to enable tool use. Returns a ChatCompletionMessage.
    """
    client = Groq(api_key=os.environ["GROQ_API_KEY"])
    kwargs = {
        "model": "llama-3.3-70b-versatile",
        "messages": messages,
    }
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"

    response = client.chat.completions.create(**kwargs)
    return response.choices[0].message
```

- [ ] **Step 2: Smoke test the LLM client manually**

```bash
python3 -c "
from agent.llm_client import chat
response = chat([{'role': 'user', 'content': 'Say hello in one word.'}])
print(response.content)
"
```

Expected: a one-word greeting like `Hello` or `Hi`. If you see an `AuthenticationError`, check your `.env` file has the right key.

- [ ] **Step 3: Commit**

```bash
git add agent/llm_client.py
git commit -m "Added LLM client wrapper for Groq, smoke tested and working"
```

---

## Task 5: Prosple Scraper

**Files:**
- Modify: `inspect_prosple.py` (throwaway — discover JSON path)
- Create: `scrapers/prosple.py`

This task has two phases: first we discover the exact path to listings inside `__NEXT_DATA__`, then we build the real scraper around that path.

- [ ] **Step 1: Update `inspect_prosple.py` to use Playwright**

Replace the full contents of `inspect_prosple.py` with:

```python
import json
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

url = "https://ph.prosple.com/internships-and-ojt-philippines"

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    page.goto(url, wait_until="networkidle", timeout=30000)
    html = page.content()
    browser.close()

soup = BeautifulSoup(html, "html.parser")
tag = soup.find("script", id="__NEXT_DATA__")

if not tag:
    print("__NEXT_DATA__ not found even with Playwright")
else:
    data = json.loads(tag.string)
    # Print just the top-level keys first
    print("Top-level keys:", list(data.keys()))
    print("\ndata['props'] keys:", list(data.get("props", {}).keys()))
    print("\ndata['props']['pageProps'] keys:", list(data.get("props", {}).get("pageProps", {}).keys()))
```

- [ ] **Step 2: Run the inspector**

```bash
python3 inspect_prosple.py
```

Expected: three lines of keys. Share the output — we need to see what's inside `pageProps` to find where the listings array lives. Once you see the output, look for a key that sounds like `jobs`, `opportunities`, `listings`, `results`, or `data`.

- [ ] **Step 3: Drill into the listings path**

Once you know which key holds the listings (e.g. `pageProps.opportunities`), update the bottom of `inspect_prosple.py` to print one listing:

```python
    # Replace the last three print lines with:
    listings = data["props"]["pageProps"]["<KEY_YOU_FOUND>"]
    print(f"\nFound {len(listings)} listings")
    print("\nFirst listing keys:", list(listings[0].keys()))
    print("\nFirst listing sample:")
    print(json.dumps(listings[0], indent=2))
```

Run again:
```bash
python3 inspect_prosple.py
```

Note the field names for: title, company, location, deadline, description, requirements, url. We'll map them in the next step.

- [ ] **Step 4: Create `scrapers/prosple.py`**

Fill in the `FIELD MAPPING` section based on what you saw in Step 3. The comments show what each variable should contain:

```python
import json
import logging
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

logger = logging.getLogger(__name__)

URL = "https://ph.prosple.com/internships-and-ojt-philippines"

# Path inside __NEXT_DATA__ to reach the listings array.
# e.g. ["props", "pageProps", "opportunities"]
# Fill this in after running inspect_prosple.py
DATA_PATH = ["props", "pageProps", "<KEY_YOU_FOUND>"]


def scrape() -> list:
    try:
        html = _fetch_html()
        raw_listings = _extract_listings(html)
        return [_normalise(r) for r in raw_listings]
    except Exception as e:
        logger.warning(f"Prosple scraper failed: {e}")
        return []


def _fetch_html() -> str:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(URL, wait_until="networkidle", timeout=30000)
        html = page.content()
        browser.close()
    return html


def _extract_listings(html: str) -> list:
    soup = BeautifulSoup(html, "html.parser")
    tag = soup.find("script", id="__NEXT_DATA__")
    if not tag:
        logger.warning("Prosple: __NEXT_DATA__ not found in page")
        return []

    data = json.loads(tag.string)
    node = data
    for key in DATA_PATH:
        node = node.get(key, {})

    if not isinstance(node, list):
        logger.warning(f"Prosple: expected a list at {DATA_PATH}, got {type(node)}")
        return []

    return node


def _normalise(raw: dict) -> dict:
    """
    Map Prosple's field names to our standard listing schema.
    Fill in the field names you found in inspect_prosple.py.
    """
    return {
        "title":        raw.get("<TITLE_FIELD>"),
        "company":      raw.get("<COMPANY_FIELD>"),
        "location":     raw.get("<LOCATION_FIELD>"),
        "deadline":     raw.get("<DEADLINE_FIELD>"),
        "compensation": raw.get("<COMPENSATION_FIELD>"),
        "description":  raw.get("<DESCRIPTION_FIELD>"),
        "requirements": raw.get("<REQUIREMENTS_FIELD>") or [],
        "source":       "prosple",
        "url":          "https://ph.prosple.com" + (raw.get("<SLUG_OR_URL_FIELD>") or ""),
    }
```

- [ ] **Step 5: Fill in the field mappings**

Based on what you saw in Step 3, replace every `<FIELD_NAME>` placeholder in `_normalise()` and `DATA_PATH` with the real field names from Prosple's JSON.

- [ ] **Step 6: Smoke test the scraper**

```bash
python3 -c "
from scrapers.prosple import scrape
listings = scrape()
print(f'Got {len(listings)} listings')
if listings:
    print('First listing:', listings[0])
"
```

Expected: a number greater than 0 and a dict with the standard schema fields.

- [ ] **Step 7: Save a fixture for tests**

```bash
python3 -c "
import json
from scrapers.prosple import scrape
listings = scrape()
with open('tests/fixtures_prosple.json', 'w') as f:
    json.dump(listings[:5], f, indent=2)
print('Saved 5 listings to tests/fixtures_prosple.json')
"
```

- [ ] **Step 8: Commit**

```bash
git add scrapers/prosple.py tests/fixtures_prosple.json
git commit -m "Prosple scraper working with Playwright — saves listings to fixtures for tests"
```

---

## Task 6: Agent Loop

**Files:**
- Create: `agent/agent.py`
- Create: `tests/test_agent.py`

The agent receives all listings, enters a loop calling tools, and stops when it calls `write_report`.

- [ ] **Step 1: Write a failing test for the agent loop**

Create `tests/test_agent.py`:

```python
from unittest.mock import patch, MagicMock
import json

SAMPLE_LISTINGS = [
    {
        "title": "Python Intern",
        "company": "Tech Co",
        "location": "Cebu",
        "deadline": "2099-12-31",
        "compensation": "Paid",
        "description": "Python Django backend work",
        "requirements": ["Python", "Django"],
        "source": "prosple",
        "url": "https://example.com/1",
    }
]


def make_tool_call(name, args):
    tc = MagicMock()
    tc.id = f"call_{name}"
    tc.function.name = name
    tc.function.arguments = json.dumps(args)
    return tc


def make_response(content=None, tool_calls=None):
    msg = MagicMock()
    msg.content = content or ""
    msg.tool_calls = tool_calls or []
    return msg


def test_agent_calls_write_report_and_returns_path(tmp_path):
    """Agent should eventually call write_report and return the output path."""
    output_file = str(tmp_path / "report.md")

    # Simulate: agent calls filter_expired, then write_report
    responses = [
        make_response(tool_calls=[make_tool_call("filter_expired", {"listings": SAMPLE_LISTINGS})]),
        make_response(tool_calls=[make_tool_call("write_report", {"listings": SAMPLE_LISTINGS})]),
    ]

    with patch("agent.agent.chat", side_effect=responses), \
         patch("agent.tools.write_report", return_value=output_file) as mock_write:
        from agent.agent import run
        result = run(SAMPLE_LISTINGS)

    mock_write.assert_called_once()
    assert result == output_file


def test_agent_stops_if_no_tool_calls():
    """Agent should not loop forever if LLM stops calling tools."""
    response = make_response(content="I'm done.", tool_calls=[])

    with patch("agent.agent.chat", return_value=response):
        from agent.agent import run
        result = run(SAMPLE_LISTINGS)

    assert result is None
```

- [ ] **Step 2: Run the test — should fail**

```bash
pytest tests/test_agent.py -v
```

Expected: `ImportError` — `agent.agent` doesn't exist yet.

- [ ] **Step 3: Create `agent/agent.py`**

```python
import json
import logging
from agent.llm_client import chat
import agent.tools as tool_fns

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an internship ranking agent for a 3rd year CS student based in Cebu, Philippines.
Their skills: Python, Django, React, AWS, Docker.

You have raw internship listings to process. Use your tools in this order:
1. filter_expired — remove listings with past deadlines
2. score_listing — score all remaining listings for relevance
3. deduplicate — merge duplicate listings across sources
4. rank_listings — sort by score
5. write_report — write the final report (call this last)

Always call write_report when you are done. Do not stop before calling it."""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "filter_expired",
            "description": "Remove listings whose deadline has already passed. Null deadlines are kept.",
            "parameters": {
                "type": "object",
                "properties": {
                    "listings": {"type": "array", "items": {"type": "object"}}
                },
                "required": ["listings"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "score_listing",
            "description": "Score each listing 0-100 for relevance. Adds a 'score' field to each listing.",
            "parameters": {
                "type": "object",
                "properties": {
                    "listings": {"type": "array", "items": {"type": "object"}}
                },
                "required": ["listings"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "deduplicate",
            "description": "Remove duplicate listings. Keeps the richest version when duplicates are found.",
            "parameters": {
                "type": "object",
                "properties": {
                    "listings": {"type": "array", "items": {"type": "object"}}
                },
                "required": ["listings"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "rank_listings",
            "description": "Sort listings by score descending.",
            "parameters": {
                "type": "object",
                "properties": {
                    "listings": {"type": "array", "items": {"type": "object"}}
                },
                "required": ["listings"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_report",
            "description": "Write the final ranked report to output/report.md. Call this when all processing is done.",
            "parameters": {
                "type": "object",
                "properties": {
                    "listings": {"type": "array", "items": {"type": "object"}}
                },
                "required": ["listings"],
            },
        },
    },
]

TOOL_MAP = {
    "filter_expired": lambda args: tool_fns.filter_expired(args["listings"]),
    "score_listing":  lambda args: tool_fns.score_listing(args["listings"]),
    "deduplicate":    lambda args: tool_fns.deduplicate(args["listings"]),
    "rank_listings":  lambda args: tool_fns.rank_listings(args["listings"]),
    "write_report":   lambda args: tool_fns.write_report(args["listings"]),
}


def run(listings: list):
    """
    Run the agentic loop. Returns the path to the written report,
    or None if the agent finished without calling write_report.
    """
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"Here are the raw internship listings to process:\n{json.dumps(listings, indent=2)}",
        },
    ]

    for iteration in range(20):  # safety limit
        response = chat(messages, tools=TOOLS)

        # Append assistant message to history
        assistant_msg = {"role": "assistant", "content": response.content or ""}
        if response.tool_calls:
            assistant_msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in response.tool_calls
            ]
        messages.append(assistant_msg)

        if not response.tool_calls:
            logger.info("Agent stopped without calling write_report")
            return None

        for tc in response.tool_calls:
            name = tc.function.name
            args = json.loads(tc.function.arguments)
            logger.info(f"[iteration {iteration}] Agent calling: {name}")

            result = TOOL_MAP[name](args)

            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": json.dumps(result),
            })

            if name == "write_report":
                logger.info(f"Report written to: {result}")
                return result

    logger.warning("Agent hit max iterations without finishing")
    return None
```

- [ ] **Step 4: Run the agent tests**

```bash
pytest tests/test_agent.py -v
```

Expected: both tests pass.

- [ ] **Step 5: Commit**

```bash
git add agent/agent.py tests/test_agent.py
git commit -m "Agent loop done — tool use working, tests passing with mocked LLM"
```

---

## Task 7: Wire It All in `main.py`

**Files:**
- Create: `main.py`

- [ ] **Step 1: Create `main.py`**

```python
import argparse
import json
import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def run_scrapers():
    from scrapers.prosple import scrape as scrape_prosple

    Path("data/raw").mkdir(parents=True, exist_ok=True)

    scrapers = [("prosple", scrape_prosple)]

    for name, fn in scrapers:
        logger.info(f"Scraping {name}...")
        listings = fn()
        path = f"data/raw/{name}.json"
        with open(path, "w") as f:
            json.dump(listings, f, indent=2)
        logger.info(f"  → saved {len(listings)} listings to {path}")


def load_raw_data() -> list:
    raw_dir = Path("data/raw")
    listings = []
    for json_file in raw_dir.glob("*.json"):
        with open(json_file) as f:
            data = json.load(f)
        listings.extend(data)
        logger.info(f"Loaded {len(data)} listings from {json_file.name}")
    return listings


def main():
    parser = argparse.ArgumentParser(description="Internship Agent")
    parser.add_argument(
        "--skip-scrape",
        action="store_true",
        help="Skip scraping and use existing data in data/raw/",
    )
    args = parser.parse_args()

    if not args.skip_scrape:
        run_scrapers()

    listings = load_raw_data()
    if not listings:
        logger.error("No listings found. Run without --skip-scrape or check scrapers.")
        sys.exit(1)

    logger.info(f"Running agent on {len(listings)} listings...")

    from agent.agent import run
    report_path = run(listings)

    if report_path:
        logger.info(f"Done! Report saved to: {report_path}")
    else:
        logger.error("Agent did not produce a report.")
        sys.exit(1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the full pipeline**

```bash
python3 main.py
```

Expected:
```
INFO: Scraping prosple...
INFO:   → saved N listings to data/raw/prosple.json
INFO: Loaded N listings from prosple.json
INFO: Running agent on N listings...
INFO: [iteration 0] Agent calling: filter_expired
INFO: [iteration 1] Agent calling: score_listing
...
INFO: Report written to: output/report.md
INFO: Done! Report saved to: output/report.md
```

- [ ] **Step 3: Open and check `output/report.md`**

```bash
cat output/report.md
```

You should see ranked internship listings with scores, locations, deadlines, and clickable links.

- [ ] **Step 4: Test `--skip-scrape`**

```bash
python3 main.py --skip-scrape
```

Expected: skips the scraping step and runs the agent on the existing `data/raw/prosple.json`.

- [ ] **Step 5: Run the full test suite one final time**

```bash
pytest tests/ -v
```

Expected: all tests pass.

- [ ] **Step 6: Delete the throwaway inspector**

```bash
rm inspect_prosple.py
```

- [ ] **Step 7: Final commit**

```bash
git add main.py
git rm inspect_prosple.py
git commit -m "Wired everything together in main.py — full pipeline working end to end"
```

---

## Done

At this point you have:
- A working Playwright scraper for Prosple
- 5 agent tools with full test coverage
- A Groq-powered agentic loop that decides when to call each tool
- A ranked markdown report as output
- A clean entry point with `--skip-scrape` flag for fast re-runs
