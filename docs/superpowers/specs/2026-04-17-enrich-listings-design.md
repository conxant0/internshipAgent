# Design: Enrich Listings from Description

**Date:** 2026-04-17
**Status:** Approved

## Goal

After fetching full description text, use a small LLM to extract structured field values and overwrite listing fields with more specific data. Priority fields are `compensation` and `deadline`; `location` and `requirements` (specific skills) are also extracted.

## Behaviour

- Runs per listing after `fetch_descriptions`, before `score_listing`.
- If a field is found in the description, overwrite the listing's existing value (even if already set) with the more specific one.
- If a field is not found, leave the existing value unchanged.
- If the description is empty or the LLM call fails, skip and log a warning.

## Fields Extracted

| Field | Type | Example |
|---|---|---|
| `compensation` | string or null | `"PHP 8000/month"` |
| `deadline` | string (YYYY-MM-DD) or null | `"2026-06-30"` |
| `location` | string or null | `"Cebu City, Philippines"` |
| `requirements` | list of strings or null | `["Python", "React", "SQL"]` |

`requirements` replaces the scraper's broad category labels (e.g. `"IT & Computer Science"`) with specific skills mentioned in the description text.

## LLM

- **Model:** `llama-3.1-8b-instant` via Groq (smaller, faster than the agent model)
- **`llm_client.chat()`** gets an optional `model` parameter (default stays `llama-3.3-70b-versatile`) so no Groq client is duplicated.

## Prompt

```
Extract the following fields from this job description. Return ONLY a JSON object.
If a field is not mentioned, return null for that key.

Fields:
- compensation: string (e.g. "PHP 8000/month") or null
- deadline: string in YYYY-MM-DD format or null
- location: string (e.g. "Cebu City, Philippines") or null
- requirements: list of specific skills (e.g. ["Python", "React", "SQL"]) or null

Description:
{description}
```

## Pipeline

```
filter_expired → fetch_descriptions → enrich_listings → score_listing → deduplicate → rank_listings → write_report
```

## Changes Required

- `agent/llm_client.py` — add optional `model` parameter to `chat()`
- `agent/tools.py` — add `enrich_listings(listings)` function
- `agent/agent.py` — add `enrich_listings` to `TOOLS`, `TOOL_MAP`, and `SYSTEM_PROMPT`

## Error Handling

- JSON parse failure: log warning, skip listing (leave fields unchanged)
- LLM call failure: log warning, skip listing
- Empty description: skip immediately without calling LLM
