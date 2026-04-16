# Fetch Full Descriptions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fetch the full job description from each listing's detail page (for non-expired listings only) and use it in scoring.

**Architecture:** A new `fetch_description(url)` function is added to `scrapers/prosple.py` using the existing `_fetch_html` + `_extract_apollo_data` helpers. A new `fetch_descriptions` tool in `agent/tools.py` dispatches to the correct scraper by `listing["source"]` via a `DESCRIPTION_FETCHERS` registry. The agent pipeline in `agent/agent.py` is updated to call this tool between `filter_expired` and `score_listing`.

**Tech Stack:** Python, Playwright, BeautifulSoup, Groq (llama-3.3-70b-versatile), pytest, unittest.mock

---

### Task 1: Add `fetch_description` to the Prosple scraper

**Files:**
- Modify: `scrapers/prosple.py`
- Create: `tests/test_prosple_fetch.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_prosple_fetch.py`:

```python
import json
from unittest.mock import patch
from scrapers.prosple import fetch_description

def _make_next_data(summary):
    return f"""<html><head><script id="__NEXT_DATA__" type="application/json">
{json.dumps({
    "props": {
        "apolloState": {
            "data": {
                "Opportunity:abc": {
                    "overview": {"summary": summary}
                }
            }
        }
    }
})}
</script></head></html>"""

def test_fetch_description_returns_summary():
    html = _make_next_data("Full job description here.")
    with patch("scrapers.prosple._fetch_html", return_value=html):
        result = fetch_description("https://ph.prosple.com/some-job")
    assert result == "Full job description here."

def test_fetch_description_returns_empty_when_no_opportunity_key():
    html = """<html><head><script id="__NEXT_DATA__" type="application/json">
{"props": {"apolloState": {"data": {"SomethingElse:123": {}}}}}
</script></head></html>"""
    with patch("scrapers.prosple._fetch_html", return_value=html):
        result = fetch_description("https://ph.prosple.com/some-job")
    assert result == ""

def test_fetch_description_returns_empty_when_no_next_data():
    with patch("scrapers.prosple._fetch_html", return_value="<html></html>"):
        result = fetch_description("https://ph.prosple.com/some-job")
    assert result == ""

def test_fetch_description_returns_empty_when_summary_missing():
    html = _make_next_data(None)
    with patch("scrapers.prosple._fetch_html", return_value=html):
        result = fetch_description("https://ph.prosple.com/some-job")
    assert result == ""
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_prosple_fetch.py -v
```

Expected: 4 failures — `ImportError: cannot import name 'fetch_description'`

- [ ] **Step 3: Refactor `_fetch_html` to accept a URL param and add `fetch_description`**

In `scrapers/prosple.py`, change `_fetch_html` signature and add `fetch_description` at the bottom:

```python
# Change this line:
def _fetch_html() -> str:
# To:
def _fetch_html(url: str = URL) -> str:
```

Then update the `page.goto` call inside it:
```python
# Change this line:
page.goto(URL, wait_until="domcontentloaded", timeout=60000)
# To:
page.goto(url, wait_until="domcontentloaded", timeout=60000)
```

Then add `fetch_description` at the bottom of the file:

```python
def fetch_description(url: str) -> str:
    """Fetch the full description from a Prosple listing detail page."""
    html = _fetch_html(url)
    apollo_data = _extract_apollo_data(html)
    for key, value in apollo_data.items():
        if key.startswith("Opportunity:"):
            return (value.get("overview") or {}).get("summary") or ""
    return ""
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_prosple_fetch.py -v
```

Expected: 4 PASSED

- [ ] **Step 5: Make sure existing scraper tests still pass**

```bash
pytest tests/ -v
```

Expected: all existing tests PASSED

- [ ] **Step 6: Commit**

```bash
git add scrapers/prosple.py tests/test_prosple_fetch.py
git commit -m "feat: add fetch_description to prosple scraper"
```

---

### Task 2: Add `fetch_descriptions` tool to `agent/tools.py`

**Files:**
- Modify: `agent/tools.py`
- Modify: `tests/test_tools.py`

- [ ] **Step 1: Write the failing tests**

Add to the bottom of `tests/test_tools.py`:

```python
from unittest.mock import patch
from agent.tools import fetch_descriptions

def test_fetch_descriptions_populates_description():
    listings = [make_listing(description="", source="prosple")]

    def mock_fetcher(url):
        return "Full description text."

    with patch.dict("agent.tools.DESCRIPTION_FETCHERS", {"prosple": mock_fetcher}, clear=True):
        result = fetch_descriptions(listings)

    assert result[0]["description"] == "Full description text."

def test_fetch_descriptions_skips_unknown_source():
    listings = [make_listing(description="", source="kalibrr")]
    result = fetch_descriptions(listings)
    assert result[0]["description"] == ""

def test_fetch_descriptions_skips_already_populated():
    listings = [make_listing(description="existing text", source="prosple")]

    called = []

    def mock_fetcher(url):
        called.append(url)
        return "new description"

    with patch.dict("agent.tools.DESCRIPTION_FETCHERS", {"prosple": mock_fetcher}, clear=True):
        result = fetch_descriptions(listings)

    assert result[0]["description"] == "existing text"
    assert len(called) == 0

def test_fetch_descriptions_continues_on_error():
    listings = [
        make_listing(description="", source="prosple", url="https://example.com/1"),
        make_listing(description="", source="prosple", url="https://example.com/2"),
    ]

    def mock_fetcher(url):
        if "1" in url:
            raise Exception("Timeout")
        return "Good description"

    with patch.dict("agent.tools.DESCRIPTION_FETCHERS", {"prosple": mock_fetcher}, clear=True):
        result = fetch_descriptions(listings)

    assert result[0]["description"] == ""
    assert result[1]["description"] == "Good description"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_tools.py::test_fetch_descriptions_populates_description -v
```

Expected: FAIL — `ImportError: cannot import name 'fetch_descriptions'`

- [ ] **Step 3: Implement `fetch_descriptions` in `agent/tools.py`**

Add these imports at the top of `agent/tools.py`:

```python
import logging
import scrapers.prosple as _prosple

logger = logging.getLogger(__name__)
```

Add the registry and function after the existing imports (before `filter_expired`):

```python
DESCRIPTION_FETCHERS = {
    "prosple": _prosple.fetch_description,
}


def fetch_descriptions(listings: List[dict]) -> List[dict]:
    """Fetch full description from each listing's detail page. Skips on error."""
    for listing in listings:
        fetcher = DESCRIPTION_FETCHERS.get(listing.get("source", ""))
        if fetcher and not listing.get("description"):
            try:
                listing["description"] = fetcher(listing["url"])
            except Exception as e:
                logger.warning(f"fetch_description failed for {listing.get('url')}: {e}")
    return listings
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_tools.py -v
```

Expected: all tests PASSED (including the 4 new ones)

- [ ] **Step 5: Commit**

```bash
git add agent/tools.py tests/test_tools.py
git commit -m "feat: add fetch_descriptions tool with source registry"
```

---

### Task 3: Wire `fetch_descriptions` into the agent pipeline

**Files:**
- Modify: `agent/agent.py`

No new tests needed — the agent loop is integration-level and covered by existing agent tests.

- [ ] **Step 1: Update the system prompt**

In `agent/agent.py`, replace `SYSTEM_PROMPT` with:

```python
SYSTEM_PROMPT = """You are an internship ranking agent for a 3rd year CS student based in Cebu, Philippines.
Their skills: Python, Django, React, AWS, Docker.

You have raw internship listings to process. Use your tools in this order:
1. filter_expired — remove listings with past deadlines
2. fetch_descriptions — fetch the full description text from each listing's detail page
3. score_listing — score all remaining listings for relevance
4. deduplicate — merge duplicate listings across sources
5. rank_listings — sort by score
6. write_report — write the final report (call this last)

Always call write_report when you are done. Do not stop before calling it."""
```

- [ ] **Step 2: Add `fetch_descriptions` to the TOOLS list**

In `agent/agent.py`, insert this entry into the `TOOLS` list after the `filter_expired` entry:

```python
    {
        "type": "function",
        "function": {
            "name": "fetch_descriptions",
            "description": "Fetch full description text from each listing's detail page. Call this after filter_expired and before score_listing.",
            "parameters": {
                "type": "object",
                "properties": {"listings": {"type": "array", "items": {"type": "object"}}},
                "required": ["listings"],
            },
        },
    },
```

- [ ] **Step 3: Add `fetch_descriptions` to TOOL_MAP**

In `agent/agent.py`, add this entry to `TOOL_MAP` after the `filter_expired` line:

```python
    "fetch_descriptions": lambda args: tool_fns.fetch_descriptions(args["listings"]),
```

- [ ] **Step 4: Update the user message in `run()`**

In `agent/agent.py`, find the user message content string and update the tool order line:

```python
# Change this line:
f"Call tools in order: filter_expired → score_listing → deduplicate → rank_listings → write_report.\n\n"
# To:
f"Call tools in order: filter_expired → fetch_descriptions → score_listing → deduplicate → rank_listings → write_report.\n\n"
```

- [ ] **Step 5: Run the full test suite**

```bash
pytest tests/ -v
```

Expected: all tests PASSED

- [ ] **Step 6: Smoke test with existing cached data**

```bash
python main.py --skip-scrape
```

Expected: agent calls tools in the new order, report written to `output/report.md`. Check the log output for the `fetch_descriptions` step being called.

- [ ] **Step 7: Commit**

```bash
git add agent/agent.py
git commit -m "feat: wire fetch_descriptions into agent pipeline"
```
