# Eligibility Parsing — Design Spec

Date: 2026-04-17

## Goal

Extract eligibility constraints from internship descriptions and surface them in the report as a new `eligibility` field. Purely informational for now; designed to be CV-matchable in the future.

## Schema Change

Add `eligibility: list[str] | None` to the listing dict, alongside the existing `requirements` field (technical skills).

Example value:
```json
["3rd year CS students only", "480 hours required", "voluntary internship only"]
```

## Prompt Change

Extend `_ENRICH_PROMPT` in `agent/tools.py` with one new field:

```
- eligibility: list of plain-English eligibility constraints — year level required, hours to render,
  internship type (voluntary/academic/for-credit), course restrictions, citizenship requirements, etc.
  Each item is a short phrase. Return null if none found.
```

## Enrichment Logic

In `enrich_listings`, add `"eligibility"` to the existing field-copy loop (one line). No new LLM call, no new pipeline step.

## Report

In `write_report`, add an `Eligibility:` line after `Skills:`, shown only when non-empty. Format: comma-separated strings.

## Pipeline Impact

None — no new tool, no new agent step, no new LLM call.

## Future CV-Matching Hook

The `eligibility` list is intentionally plain strings so a future `match_cv(listing, cv_data)` function can scan each string against parsed CV fields (year level, course, hours available, internship type preference).
