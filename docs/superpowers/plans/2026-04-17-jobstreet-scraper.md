# JobStreet Scraper Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `scrapers/jobstreet.py` that calls JobStreet's REST API to fetch ICT internship listings in the Philippines and integrates into the existing pipeline.

**Architecture:** A `requests`-based scraper (no Playwright) calls `https://ph.jobstreet.com/api/jobsearch/v5/search` with fixed ICT/Philippines parameters, paginates using `totalCount`, and normalises each listing to the standard schema. The scraper is registered in `main.py`; no other files need changes.

**Tech Stack:** Python `requests`, existing `scrapers/` pattern, `pytest` + `unittest.mock`

---

### Task 1: Write and pass normalise tests

**Files:**
- Create: `tests/test_jobstreet.py`
- Create: `scrapers/jobstreet.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_jobstreet.py`:

```python
import pytest
from unittest.mock import patch, MagicMock
from scrapers.jobstreet import _normalise, scrape


def _make_raw(**kwargs):
    base = {
        "id": "12345678",
        "title": "IT Intern",
        "companyName": "Acme Corp",
        "locations": [{"label": "Cebu City, Central Visayas"}],
        "salaryLabel": "₱15,000 – ₱20,000 per month",
        "teaser": "You will build internal tools using Python.",
        "workTypes": ["Intern"],
        "workArrangements": [],
    }
    base.update(kwargs)
    return base


def test_normalise_maps_all_fields():
    raw = _make_raw()
    result = _normalise(raw)
    assert result["title"] == "IT Intern"
    assert result["company"] == "Acme Corp"
    assert result["location"] == "Cebu City, Central Visayas"
    assert result["deadline"] is None
    assert result["compensation"] == "₱15,000 – ₱20,000 per month"
    assert result["description"] == "You will build internal tools using Python."
    assert result["requirements"] == []
    assert result["source"] == "jobstreet"
    assert result["url"] == "https://ph.jobstreet.com/job/12345678"


def test_normalise_no_salary():
    raw = _make_raw(salaryLabel="")
    result = _normalise(raw)
    assert result["compensation"] is None


def test_normalise_no_locations():
    raw = _make_raw(locations=[])
    result = _normalise(raw)
    assert result["location"] is None


def test_normalise_no_teaser():
    raw = _make_raw(teaser="")
    result = _normalise(raw)
    assert result["description"] == ""
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_jobstreet.py -v
```

Expected: `ImportError` or `ModuleNotFoundError` — `scrapers/jobstreet.py` doesn't exist yet.

- [ ] **Step 3: Create minimal `scrapers/jobstreet.py` with `_normalise`**

```python
import logging
import requests

logger = logging.getLogger(__name__)

_BASE_URL = "https://ph.jobstreet.com/api/jobsearch/v5/search"
_PAGE_SIZE = 32
_PARAMS = {
    "siteKey": "PH",
    "keywords": "Intern",
    "classification": "6281",
    "where": "Philippines",
    "locale": "en-PH",
    "pageSize": _PAGE_SIZE,
}
_HEADERS = {
    "Accept": "application/json",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": "https://ph.jobstreet.com/Intern-jobs-in-information-communication-technology/in-Philippines",
}


def scrape() -> list:
    try:
        results = []
        page = 1
        total = None
        while True:
            data = _fetch_page(page)
            if total is None:
                total = data.get("totalCount", 0)
            items = data.get("data", [])
            if not items:
                break
            results.extend(_normalise(item) for item in items)
            if len(results) >= total:
                break
            page += 1
        return results
    except Exception as e:
        logger.warning(f"JobStreet scraper failed: {e}")
        return []


def _fetch_page(page: int) -> dict:
    params = {**_PARAMS, "page": page}
    resp = requests.get(_BASE_URL, params=params, headers=_HEADERS, timeout=20)
    resp.raise_for_status()
    return resp.json()


def _normalise(raw: dict) -> dict:
    locations = raw.get("locations") or []
    location = locations[0]["label"] if locations else None

    salary = raw.get("salaryLabel") or ""
    compensation = salary if salary else None

    return {
        "title": raw.get("title"),
        "company": raw.get("companyName"),
        "location": location,
        "deadline": None,
        "compensation": compensation,
        "description": raw.get("teaser") or "",
        "requirements": [],
        "source": "jobstreet",
        "url": f"https://ph.jobstreet.com/job/{raw['id']}",
    }
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_jobstreet.py -v
```

Expected: 4 tests pass.

- [ ] **Step 5: Commit**

```bash
git add scrapers/jobstreet.py tests/test_jobstreet.py
git commit -m "feat: add jobstreet scraper with normalise tests"
```

---

### Task 2: Write and pass pagination tests

**Files:**
- Modify: `tests/test_jobstreet.py`

- [ ] **Step 1: Add pagination tests**

Append to `tests/test_jobstreet.py`:

```python
def test_scrape_paginates_until_total_count():
    page1 = {"totalCount": 40, "data": [_make_raw(id=str(i)) for i in range(32)]}
    page2 = {"totalCount": 40, "data": [_make_raw(id=str(i)) for i in range(32, 40)]}

    with patch("scrapers.jobstreet._fetch_page", side_effect=[page1, page2]) as mock_fetch:
        results = scrape()

    assert mock_fetch.call_count == 2
    assert len(results) == 40


def test_scrape_stops_on_empty_page():
    page1 = {"totalCount": 10, "data": [_make_raw(id=str(i)) for i in range(10)]}
    page2 = {"totalCount": 10, "data": []}

    with patch("scrapers.jobstreet._fetch_page", side_effect=[page1, page2]):
        results = scrape()

    assert len(results) == 10


def test_scrape_returns_empty_on_error():
    with patch("scrapers.jobstreet._fetch_page", side_effect=Exception("network error")):
        results = scrape()

    assert results == []
```

- [ ] **Step 2: Run tests to verify new ones fail**

```bash
pytest tests/test_jobstreet.py::test_scrape_paginates_until_total_count tests/test_jobstreet.py::test_scrape_stops_on_empty_page tests/test_jobstreet.py::test_scrape_returns_empty_on_error -v
```

Expected: 3 tests FAIL (scrape not yet wired to `_fetch_page` as a mockable call).

- [ ] **Step 3: Run the full test suite to confirm existing tests still pass**

```bash
pytest tests/test_jobstreet.py -v
```

Expected: normalise tests pass, pagination tests fail.

- [ ] **Step 4: Verify `scrape()` in `scrapers/jobstreet.py` already matches the mock-friendly pattern**

The `scrape()` implementation in Task 1 already calls `_fetch_page(page)` directly, which `unittest.mock.patch` can intercept. No code changes needed — run the tests.

```bash
pytest tests/test_jobstreet.py -v
```

Expected: all 7 tests pass.

- [ ] **Step 5: Commit**

```bash
git add tests/test_jobstreet.py
git commit -m "test: add jobstreet pagination and error tests"
```

---

### Task 3: Register scraper in main.py

**Files:**
- Modify: `main.py`

- [ ] **Step 1: Add the import and register in `run_scrapers()`**

In `main.py`, change:

```python
def run_scrapers():
    from scrapers.prosple import scrape as scrape_prosple

    (BASE / "data" / "raw").mkdir(parents=True, exist_ok=True)

    for name, fn in [("prosple", scrape_prosple)]:
```

To:

```python
def run_scrapers():
    from scrapers.prosple import scrape as scrape_prosple
    from scrapers.jobstreet import scrape as scrape_jobstreet

    (BASE / "data" / "raw").mkdir(parents=True, exist_ok=True)

    for name, fn in [("prosple", scrape_prosple), ("jobstreet", scrape_jobstreet)]:
```

- [ ] **Step 2: Run full test suite to confirm nothing broken**

```bash
pytest -v
```

Expected: all tests pass.

- [ ] **Step 3: Smoke-test the scraper directly**

```bash
python3 -c "from scrapers.jobstreet import scrape; r = scrape(); print(f'{len(r)} listings'); print(r[0] if r else 'empty')"
```

Expected: prints a count > 0 and a dict with keys `title`, `company`, `location`, `deadline`, `compensation`, `description`, `requirements`, `source`, `url`.

- [ ] **Step 4: Commit**

```bash
git add main.py
git commit -m "feat: register jobstreet scraper in pipeline"
```

---

### Task 4: End-to-end verification

**Files:** none — verification only

- [ ] **Step 1: Run pipeline with both scrapers**

```bash
python3 main.py
```

Expected:
- Logs show `Scraping prosple...` and `Scraping jobstreet...`
- Both save JSON files to `data/raw/`
- Agent runs on the combined listing count
- `output/report.md` is written

- [ ] **Step 2: Check that both sources appear in the report**

```bash
grep -c "jobstreet\|prosple" data/raw/jobstreet.json data/raw/prosple.json
```

Expected: both files exist and contain listings.

- [ ] **Step 3: Commit probe scripts cleanup (optional)**

The probe scripts in `scripts/` are already committed as reference. No action needed unless you want to remove them:

```bash
# Only if you want to remove probe scripts:
# git rm scripts/probe_jobstreet*.py
# git commit -m "chore: remove jobstreet probe scripts"
```
