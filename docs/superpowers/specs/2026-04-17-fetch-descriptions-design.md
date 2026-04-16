# Design: Fetch Full Descriptions for Scoring

**Date:** 2026-04-17
**Status:** Approved

## Goal

Populate the `description` field on surviving listings by visiting each listing's detail page, so that `score_listing` has full text to match skills against rather than an empty string.

## Scope

Fetching and storing full descriptions only. Extracting structured fields (compensation, location, skills) from description text is a separate future feature.

## Architecture

### New scraper contract

Each scraper module must expose two functions:

- `scrape() -> list[dict]` — existing, fetches the list page
- `fetch_description(url: str) -> str` — new, fetches the full description from a single detail page

`fetch_description` contains source-specific extraction logic. If a scraper doesn't implement it, that source is silently skipped during enrichment (description stays empty).

### New agent tool: `fetch_descriptions`

Added to `agent/tools.py`. Dispatches to the correct fetcher by `listing["source"]` using a registry dict:

```python
DESCRIPTION_FETCHERS = {
    "prosple": prosple.fetch_description,
    # new sources registered here
}

def fetch_descriptions(listings: list[dict]) -> list[dict]:
    for listing in listings:
        fetcher = DESCRIPTION_FETCHERS.get(listing["source"])
        if fetcher and not listing.get("description"):
            try:
                listing["description"] = fetcher(listing["url"])
            except Exception as e:
                logger.warning(f"fetch_description failed for {listing['url']}: {e}")
    return listings
```

Only visits detail pages for listings that:
- Have a registered fetcher for their source
- Don't already have a description (avoids redundant fetches)

If `fetch_description` raises for any reason (timeout, unexpected page structure, network error), that listing's `description` stays empty and the loop continues. The listing is not dropped — it still gets scored and ranked on its other fields.

### Pipeline change

`agent/agent.py` system prompt and `TOOLS` list updated to insert `fetch_descriptions` between `filter_expired` and `score_listing`:

```
filter_expired → fetch_descriptions → score_listing → deduplicate → rank_listings → write_report
```

### Prosple implementation

`scrapers/prosple.py` gains `fetch_description(url: str) -> str`:

1. Launch Playwright Chromium (headless)
2. Navigate to `url`
3. Extract `__NEXT_DATA__` script tag
4. Parse apolloState, find the `Opportunity:*` key
5. Return `(opportunity.get("overview") or {}).get("summary") or ""`

The browser session is opened and closed per call (same pattern as existing `_fetch_html`). A single shared browser session across all listings in `fetch_descriptions` would be faster but is an optimisation left for later.

## Data flow

```
data/raw/prosple.json          (description = "")
        ↓
filter_expired                 (drops expired listings)
        ↓
fetch_descriptions             (description = full text from detail page)
        ↓
score_listing                  (skills now matched against full description)
        ↓
deduplicate → rank → report
```

## Adding a new source

1. Create `scrapers/<source>.py` with `scrape()` and `fetch_description(url)`
2. Register `scrape()` in `main.py` `run_scrapers()`
3. Register `fetch_description` in `DESCRIPTION_FETCHERS` in `agent/tools.py`

## Testing

- Unit test for `fetch_descriptions` tool: mock `DESCRIPTION_FETCHERS`, assert descriptions are populated and unknown sources are skipped
- Unit test for `fetch_description` in `scrapers/prosple.py`: mock Playwright, assert correct field is extracted from a fixture `__NEXT_DATA__` payload
- Existing `score_listing` tests remain valid — no changes to scoring logic
