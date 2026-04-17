---
title: JobStreet Scraper
date: 2026-04-17
status: approved
---

# JobStreet Scraper Design

## Overview

Add `scrapers/jobstreet.py` as a second internship source alongside Prosple. The scraper calls JobStreet's internal REST API directly using `requests` (no Playwright required), paginates through all results, normalises each listing to the standard schema, and integrates into the existing pipeline with no changes to `agent/tools.py`.

## Discovery

Confirmed via network probing:
- JobStreet has no `__NEXT_DATA__` (unlike Prosple)
- Job cards are server-side rendered into `article[data-job-id]` elements
- `window.SEEK_CONFIG` exposes a REST API at `/api/jobsearch/v5/search`
- The REST API returns clean JSON with no authentication required
- `totalCount` in the response enables clean pagination termination

## Architecture

The scraper fits the existing pattern: one `scrape() -> list[dict]` function, registered in `main.py`'s `run_scrapers()`. No other files need changes beyond `main.py`.

```
scrapers/jobstreet.py
  scrape()            — entry point, paginates until exhausted
  _fetch_page(page)   — single GET to /api/jobsearch/v5/search
  _normalise(raw)     — maps API fields → standard listing schema
```

## API Details

**Endpoint:** `https://ph.jobstreet.com/api/jobsearch/v5/search`

**Fixed parameters:**
| Param | Value |
|---|---|
| `siteKey` | `PH` |
| `keywords` | `Intern` |
| `classification` | `6281` (Information & Communication Technology) |
| `where` | `Philippines` |
| `locale` | `en-PH` |
| `pageSize` | `32` |
| `page` | `1, 2, 3, ...` |

**Pagination:** loop while `(page - 1) * PAGE_SIZE < totalCount` and response returns results. Stop early if a page returns 0 items.

## Field Mapping

| Standard field | Source |
|---|---|
| `title` | `raw["title"]` |
| `company` | `raw["companyName"]` |
| `location` | `raw["locations"][0]["label"]` if present, else `None` |
| `deadline` | `None` (not available in listing API) |
| `compensation` | `raw["salaryLabel"]` if non-empty, else `None` |
| `description` | `raw["teaser"]` (short summary, already populated) |
| `requirements` | `[]` (populated later by `enrich_listings`) |
| `source` | `"jobstreet"` |
| `url` | `https://ph.jobstreet.com/job/{raw["id"]}` |

## Description Strategy

Using the `teaser` field (1–2 sentence summary from the API) as the initial `description`. Because `description` is non-empty, `fetch_descriptions` will skip these listings automatically — no Playwright detail-page fetching needed. The `enrich_listings` LLM step works from the teaser text.

This is intentional for now. A future improvement could add a `fetch_description` that parses the detail page HTML for the full job description.

## Integration

**`main.py`** — add to `run_scrapers()`:
```python
from scrapers.jobstreet import scrape as scrape_jobstreet
# ...
for name, fn in [("prosple", scrape_prosple), ("jobstreet", scrape_jobstreet)]:
```

**`agent/tools.py`** — no changes needed. `jobstreet` is already listed in `deduplicate`'s `source_priority` at rank 2 (prosple=0, kalibrr=1, jobstreet=2).

**`DESCRIPTION_FETCHERS`** — no entry added (teaser strategy).

## Testing

- Unit test: `_normalise()` with a fixture dict produces a valid listing with all required keys
- Unit test: pagination stops when `totalCount` is reached
- Integration test (manual): `python main.py` with both scrapers produces a combined report with listings from both sources
