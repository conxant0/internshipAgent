# Resume-Based Scoring Design

**Date:** 2026-04-17

## Overview

Replace the current hardcoded heuristic scoring in `score_listing` with LLM-driven scoring personalized to the user's resume and preferences. The user provides a resume once (PDF or DOCX) and a `preferences.json` file. The resume is parsed into a structured profile JSON and cached locally. Both the profile and preferences are passed to the LLM at score time to evaluate each listing.

## Required Inputs

Two files must be present before the pipeline runs:

| File | Purpose |
|---|---|
| `data/resume.pdf` or `data/resume.docx` | Source for extracting the user's skills, degree, year level, and experience |
| `data/preferences.json` | User-defined target role and location preference (not derivable from resume) |

`data/preferences.json` schema:
```json
{
  "target_role": "Software Engineering",
  "location_preference": "Cebu"
}
```

## Data Flow

```
data/resume.pdf (or .docx)   data/preferences.json
         ↓                            ↓
resume_parser.py  — extracts text, calls LLM once to produce structured profile
         ↓
data/profile.json — cached, reused on subsequent runs
         ↓
main.py           — loads profile.json + preferences.json before agent loop
         ↓
agent/tools.py    — score_listing receives profile + preferences + listing, calls LLM
                    LLM returns { "score": int, "rationale": str }
         ↓
report            — each listing shows score + 2–3 sentence rationale
```

## Profile Schema

```json
{
  "skills": ["Python", "SQL", "React"],
  "degree": "BS Computer Science",
  "year_level": "3rd year",
  "experience_summary": "Brief summary of relevant experience and projects"
}
```

## Scoring Framework

The LLM scores each listing 0–100 using this fixed framework. The prompt explicitly instructs the LLM to weight each dimension as specified — scores are not purely subjective.

| Dimension | Weight | Guidance |
|---|---|---|
| Skills match | 25 | How well the user's existing skills align with what the listing requires |
| Role relevance | 20 | How closely the listing title and responsibilities match the user's target role |
| Eligibility fit | 20 | Whether the user meets year level, degree, citizenship, or hours requirements |
| Location | 20 | Cebu-based or remote = full points; onsite Manila or other PH cities = partial; international onsite = low |
| Compensation | 15 | Paid internships score higher; unpaid or unspecified score lower |

Location scoring uses `preferences.location_preference` from `preferences.json`. Role relevance uses `preferences.target_role`.

## Components

### `resume_parser.py` (new)

- Accepts `data/resume.pdf` or `data/resume.docx` (checks both, errors if neither found)
- Extracts raw text via `pdfplumber` (PDF) or `python-docx` (DOCX)
- Calls LLM once with raw text to extract structured profile
- Saves result to `data/profile.json`
- If `data/profile.json` already exists, skips parsing (delete to force refresh)

### `agent/tools.py` — `score_listing` rewrite

- Removes all heuristic scoring logic
- Accepts the cached profile dict and preferences dict as parameters
- Calls LLM with profile JSON + preferences JSON + listing fields (title, company, location, description, requirements, eligibility)
- LLM prompt includes the scoring framework weights explicitly
- LLM returns `{"score": int, "rationale": str}` where score is 0–100 and rationale is 2–3 sentences
- One retry on malformed JSON response; raises with raw output on second failure

### `main.py`

- Before starting the agent loop:
  - Checks for `data/preferences.json` — raises `FileNotFoundError` with message: `"No preferences.json found at data/preferences.json. Please create it with your target_role and location_preference."` if missing
  - Checks for `data/profile.json` — if missing, calls `resume_parser.py` to generate it
  - If no resume file found during parsing: raises `FileNotFoundError` with message: `"No resume found at data/resume.pdf (or .docx). Please add your resume to get started."`

### Report (`write_report`)

- Updated to display the LLM rationale (2–3 sentences) under each listing's score

## Error Handling

| Scenario | Behavior |
|---|---|
| `data/preferences.json` missing | Raise `FileNotFoundError` with clear message, exit immediately |
| No resume file at `data/resume.pdf` or `.docx` | Raise `FileNotFoundError` with clear message, exit immediately |
| LLM returns malformed score/rationale JSON | Retry once; raise with raw LLM output on second failure |

## Testing

- `tests/test_resume_parser.py` (new) — mock LLM call, assert profile JSON has correct shape and field types
- `tests/test_tools.py` — add tests for new `score_listing` with sample profile + preferences + listing; assert score is int in 0–100 range and rationale is non-empty string; remove old heuristic scoring tests

## Dependencies

New packages required:
- `pdfplumber` — PDF text extraction
- `python-docx` — DOCX text extraction
