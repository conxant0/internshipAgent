# Resume-Based Scoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace hardcoded heuristic scoring with LLM-driven scoring personalized to the user's resume and preferences.

**Architecture:** A new `resume_parser.py` extracts a structured profile from the user's resume (PDF/DOCX) and caches it to `data/profile.json`. `main.py` loads `data/preferences.json` and the cached profile before the agent loop and passes them to `agent.run()`. The `score_listing` tool calls the LLM with the profile, preferences, and listing to produce a 0–100 score and 2–3 sentence rationale, which is displayed in the report.

**Tech Stack:** Python, pdfplumber, python-docx, Groq LLM (llama-3.3-70b-versatile), pytest

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `resume_parser.py` | Create | Extract text from PDF/DOCX, call LLM to produce profile JSON, cache to `data/profile.json` |
| `agent/tools.py` | Modify | Rewrite `score_listing` to use LLM with profile+preferences; update `write_report` to show rationale |
| `agent/agent.py` | Modify | Pass profile+preferences through `run()` into `score_listing` via TOOL_MAP closure; remove hardcoded student profile from SYSTEM_PROMPT |
| `main.py` | Modify | Validate `preferences.json` exists, generate/load `profile.json`, pass both to `agent.run()` |
| `requirements.txt` | Modify | Add `pdfplumber` and `python-docx` |
| `tests/test_resume_parser.py` | Create | Tests for resume parsing and profile caching |
| `tests/test_tools.py` | Modify | Remove old heuristic score tests; add new LLM-based score tests and rationale display tests |

---

### Task 1: Add dependencies

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Add packages to requirements.txt**

Replace the contents of `requirements.txt` with:

```
playwright==1.44.0
beautifulsoup4==4.12.3
groq==0.9.0
python-dotenv==1.0.1
pytest==8.2.0
pdfplumber==0.11.4
python-docx==1.1.2
```

- [ ] **Step 2: Install new dependencies**

Run: `pip install pdfplumber==0.11.4 python-docx==1.1.2`
Expected: Both packages install without errors.

- [ ] **Step 3: Commit**

```bash
git add requirements.txt
git commit -m "chore: add pdfplumber and python-docx dependencies"
```

---

### Task 2: Create resume_parser.py

**Files:**
- Create: `resume_parser.py`
- Create: `tests/test_resume_parser.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_resume_parser.py`:

```python
import json
import os
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


def _mock_chat_response(content: str):
    msg = MagicMock()
    msg.content = content
    return msg


SAMPLE_PROFILE_JSON = json.dumps({
    "skills": ["Python", "SQL", "React"],
    "degree": "BS Computer Science",
    "year_level": "3rd year",
    "experience_summary": "Built web apps using Django and React."
})


def test_parse_resume_returns_profile_dict(tmp_path):
    resume = tmp_path / "resume.pdf"
    resume.write_bytes(b"%PDF fake content")

    with patch("resume_parser._extract_text", return_value="resume text here"), \
         patch("resume_parser.chat", return_value=_mock_chat_response(SAMPLE_PROFILE_JSON)):
        from resume_parser import parse_resume
        profile = parse_resume(data_dir=tmp_path)

    assert isinstance(profile["skills"], list)
    assert isinstance(profile["degree"], str)
    assert isinstance(profile["year_level"], str)
    assert isinstance(profile["experience_summary"], str)


def test_parse_resume_saves_profile_json(tmp_path):
    resume = tmp_path / "resume.pdf"
    resume.write_bytes(b"%PDF fake content")

    with patch("resume_parser._extract_text", return_value="resume text here"), \
         patch("resume_parser.chat", return_value=_mock_chat_response(SAMPLE_PROFILE_JSON)):
        from resume_parser import parse_resume
        parse_resume(data_dir=tmp_path)

    assert (tmp_path / "profile.json").exists()
    saved = json.loads((tmp_path / "profile.json").read_text())
    assert saved["skills"] == ["Python", "SQL", "React"]


def test_parse_resume_skips_when_profile_is_newer(tmp_path):
    resume = tmp_path / "resume.pdf"
    resume.write_bytes(b"%PDF fake content")

    existing_profile = {"skills": ["Java"], "degree": "BS IT", "year_level": "4th year", "experience_summary": "Old."}
    profile_path = tmp_path / "profile.json"
    profile_path.write_text(json.dumps(existing_profile))

    # Make profile.json newer than resume
    future_time = os.path.getmtime(resume) + 100
    os.utime(profile_path, (future_time, future_time))

    called = []
    with patch("resume_parser.chat", side_effect=lambda *a, **kw: called.append(1)):
        from resume_parser import parse_resume
        profile = parse_resume(data_dir=tmp_path)

    assert len(called) == 0
    assert profile["skills"] == ["Java"]


def test_parse_resume_reparses_when_resume_is_newer(tmp_path):
    resume = tmp_path / "resume.pdf"
    resume.write_bytes(b"%PDF fake content")

    old_profile = {"skills": ["Java"], "degree": "BS IT", "year_level": "4th year", "experience_summary": "Old."}
    profile_path = tmp_path / "profile.json"
    profile_path.write_text(json.dumps(old_profile))

    # Make resume newer than profile.json
    future_time = os.path.getmtime(profile_path) + 100
    os.utime(resume, (future_time, future_time))

    with patch("resume_parser._extract_text", return_value="new resume text"), \
         patch("resume_parser.chat", return_value=_mock_chat_response(SAMPLE_PROFILE_JSON)):
        from resume_parser import parse_resume
        profile = parse_resume(data_dir=tmp_path)

    assert profile["skills"] == ["Python", "SQL", "React"]


def test_parse_resume_raises_when_no_resume(tmp_path):
    from resume_parser import parse_resume
    with pytest.raises(FileNotFoundError, match="No resume found"):
        parse_resume(data_dir=tmp_path)


def test_parse_resume_accepts_docx(tmp_path):
    resume = tmp_path / "resume.docx"
    resume.write_bytes(b"fake docx content")

    with patch("resume_parser._extract_text", return_value="resume text"), \
         patch("resume_parser.chat", return_value=_mock_chat_response(SAMPLE_PROFILE_JSON)):
        from resume_parser import parse_resume
        profile = parse_resume(data_dir=tmp_path)

    assert profile["skills"] == ["Python", "SQL", "React"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_resume_parser.py -v`
Expected: All tests FAIL with `ModuleNotFoundError: No module named 'resume_parser'`

- [ ] **Step 3: Implement resume_parser.py**

Create `resume_parser.py` in the project root:

```python
import json
import os
from pathlib import Path

from agent.llm_client import chat

_PARSE_MODEL = "llama-3.3-70b-versatile"

_PARSE_PROMPT = """Extract the following fields from this resume. Return ONLY a JSON object with no extra text.

Fields:
- skills: list of technical skills, tools, and programming languages (e.g. ["Python", "SQL", "React"])
- degree: degree program (e.g. "BS Computer Science") or null
- year_level: current year level (e.g. "3rd year") or null
- experience_summary: 2-3 sentence summary of relevant experience and projects, or null

Resume:
{resume_text}"""

BASE = Path(__file__).parent


def _extract_text(resume_path: Path) -> str:
    suffix = resume_path.suffix.lower()
    if suffix == ".pdf":
        import pdfplumber
        with pdfplumber.open(resume_path) as pdf:
            return "\n".join(page.extract_text() or "" for page in pdf.pages)
    elif suffix in (".docx", ".doc"):
        from docx import Document
        doc = Document(resume_path)
        return "\n".join(p.text for p in doc.paragraphs)
    else:
        raise ValueError(f"Unsupported file type: {resume_path.suffix}")


def _find_resume(data_dir: Path) -> Path:
    for ext in (".pdf", ".docx"):
        candidate = data_dir / f"resume{ext}"
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        "No resume found at data/resume.pdf (or .docx). Please add your resume to get started."
    )


def parse_resume(data_dir: Path = None) -> dict:
    """Parse resume and return profile dict. Saves result to data/profile.json.
    Skips parsing if profile.json is newer than the resume file."""
    if data_dir is None:
        data_dir = BASE / "data"

    profile_path = data_dir / "profile.json"
    resume_path = _find_resume(data_dir)

    if profile_path.exists() and os.path.getmtime(profile_path) > os.path.getmtime(resume_path):
        with open(profile_path) as f:
            return json.load(f)

    resume_text = _extract_text(resume_path)
    response = chat(
        [{"role": "user", "content": _PARSE_PROMPT.format(resume_text=resume_text)}],
        model=_PARSE_MODEL,
    )
    content = response.content.strip()
    if content.startswith("```"):
        content = content.split("```", 2)[1]
        if content.startswith("json"):
            content = content[4:]
        content = content.rsplit("```", 1)[0].strip()

    profile = json.loads(content)

    with open(profile_path, "w") as f:
        json.dump(profile, f, indent=2)

    return profile
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_resume_parser.py -v`
Expected: All 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add resume_parser.py tests/test_resume_parser.py
git commit -m "feat: add resume_parser to extract profile from PDF/DOCX"
```

---

### Task 3: Rewrite score_listing in tools.py

**Files:**
- Modify: `agent/tools.py` (lines 76–117 — `score_listing` and `_compute_score`)
- Modify: `tests/test_tools.py` (lines 43–67 — old score_listing tests)

- [ ] **Step 1: Remove old heuristic score tests and add new LLM-based score tests**

In `tests/test_tools.py`, replace the entire `# ── score_listing ──` section (lines 43–67):

```python
# ── score_listing ─────────────────────────────────────────────────────────────

from unittest.mock import patch, MagicMock

SAMPLE_PROFILE = {
    "skills": ["Python", "Django", "React"],
    "degree": "BS Computer Science",
    "year_level": "3rd year",
    "experience_summary": "Built web apps using Django and React.",
}

SAMPLE_PREFERENCES = {
    "target_role": "Software Engineering",
    "location_preference": "Cebu",
}


def _mock_score_response(score: int, rationale: str):
    import json
    msg = MagicMock()
    msg.content = json.dumps({"score": score, "rationale": rationale})
    return msg


def test_score_listing_returns_int(monkeypatch):
    listing = make_listing()
    with patch("agent.tools.chat", return_value=_mock_score_response(75, "Good match.")):
        scores = score_listing([listing], SAMPLE_PROFILE, SAMPLE_PREFERENCES)
    assert isinstance(scores[0]["score"], int)


def test_score_listing_score_is_between_0_and_100(monkeypatch):
    listing = make_listing()
    with patch("agent.tools.chat", return_value=_mock_score_response(82, "Strong match.")):
        scores = score_listing([listing], SAMPLE_PROFILE, SAMPLE_PREFERENCES)
    assert 0 <= scores[0]["score"] <= 100


def test_score_listing_includes_rationale(monkeypatch):
    listing = make_listing()
    with patch("agent.tools.chat", return_value=_mock_score_response(70, "Skills align well with listing requirements.")):
        scores = score_listing([listing], SAMPLE_PROFILE, SAMPLE_PREFERENCES)
    assert isinstance(scores[0]["rationale"], str)
    assert len(scores[0]["rationale"]) > 0


def test_score_listing_retries_on_bad_json(monkeypatch):
    listing = make_listing()
    bad_msg = MagicMock()
    bad_msg.content = "not valid json"
    good_msg = MagicMock()
    good_msg.content = '{"score": 60, "rationale": "Recovered after retry."}'

    with patch("agent.tools.chat", side_effect=[bad_msg, good_msg]):
        scores = score_listing([listing], SAMPLE_PROFILE, SAMPLE_PREFERENCES)
    assert scores[0]["score"] == 60


def test_score_listing_raises_after_two_bad_responses(monkeypatch):
    listing = make_listing()
    bad_msg = MagicMock()
    bad_msg.content = "not valid json"

    with patch("agent.tools.chat", return_value=bad_msg):
        with pytest.raises(ValueError, match="score_listing failed"):
            score_listing([listing], SAMPLE_PROFILE, SAMPLE_PREFERENCES)
```

- [ ] **Step 2: Run new score tests to verify they fail**

Run: `pytest tests/test_tools.py::test_score_listing_returns_int -v`
Expected: FAIL — `score_listing()` still has old heuristic signature (no profile/preferences args)

- [ ] **Step 3: Rewrite score_listing and remove _compute_score in tools.py**

Replace lines 76–117 in `agent/tools.py` (the entire `score_listing` and `_compute_score` functions):

```python
_SCORE_MODEL = "llama-3.3-70b-versatile"

_SCORE_PROMPT = """Score this internship listing for the candidate below. Return ONLY a JSON object.

Scoring framework (total = 100 pts):
- Skills match (25 pts): How well the candidate's existing skills align with the listing's requirements.
- Role relevance (20 pts): How closely the listing title and responsibilities match the candidate's target role: {target_role}.
- Eligibility fit (20 pts): Whether the candidate meets year level, degree, citizenship, or hours requirements.
- Location (20 pts): Candidate prefers {location_preference}. Cebu-based or remote = 20 pts; onsite in other PH cities = 10 pts; international onsite = 2 pts.
- Compensation (15 pts): Paid = 15 pts; unpaid = 0 pts; unspecified = 7 pts.

Candidate profile:
{profile_json}

Listing:
Title: {title}
Company: {company}
Location: {location}
Description: {description}
Requirements: {requirements}
Eligibility: {eligibility}

Return ONLY: {{"score": <int 0-100>, "rationale": "<2-3 sentence explanation of the score>"}}"""


def score_listing(listings: List[dict], profile: dict, preferences: dict) -> List[dict]:
    """Score each listing 0-100 using LLM with the user's profile and preferences."""
    import json as _json
    result = []
    for listing in listings:
        scored = dict(listing)
        prompt = _SCORE_PROMPT.format(
            target_role=preferences.get("target_role", ""),
            location_preference=preferences.get("location_preference", ""),
            profile_json=_json.dumps(profile, indent=2),
            title=listing.get("title") or "",
            company=listing.get("company") or "",
            location=listing.get("location") or "Not specified",
            description=listing.get("description") or "",
            requirements=", ".join(listing.get("requirements") or []) or "Not specified",
            eligibility=", ".join(listing.get("eligibility") or []) or "Not specified",
        )
        raw = None
        for attempt in range(2):
            try:
                response = chat(
                    [{"role": "user", "content": prompt}],
                    model=_SCORE_MODEL,
                )
                content = response.content.strip()
                if content.startswith("```"):
                    content = content.split("```", 2)[1]
                    if content.startswith("json"):
                        content = content[4:]
                    content = content.rsplit("```", 1)[0].strip()
                parsed = _json.loads(content)
                scored["score"] = int(parsed["score"])
                scored["rationale"] = parsed["rationale"]
                break
            except Exception:
                raw = getattr(response, "content", None) if "response" in dir() else None
        else:
            raise ValueError(f"score_listing failed after 2 attempts. Last LLM output: {raw!r}")
        result.append(scored)
    return result
```

- [ ] **Step 4: Run new score tests to verify they pass**

Run: `pytest tests/test_tools.py -k "score_listing" -v`
Expected: All 5 new score tests PASS

- [ ] **Step 5: Run full test suite to check for regressions**

Run: `pytest tests/test_tools.py -v`
Expected: All tests PASS (the old heuristic tests were replaced, not just removed)

- [ ] **Step 6: Commit**

```bash
git add agent/tools.py tests/test_tools.py
git commit -m "feat: rewrite score_listing to use LLM with resume profile and preferences"
```

---

### Task 4: Update write_report to show rationale

**Files:**
- Modify: `agent/tools.py` (`write_report` function, lines 153–199)
- Modify: `tests/test_tools.py` (add rationale display test)

- [ ] **Step 1: Write the failing test**

Add to the `# ── write_report ──` section in `tests/test_tools.py`:

```python
def test_write_report_shows_rationale(tmp_path):
    listing = make_listing(score=85, rationale="Strong Python skills match. Cebu location is ideal. Paid internship.")
    output_file = str(tmp_path / "report.md")
    write_report([listing], output_path=output_file)
    content = open(output_file).read()
    assert "Strong Python skills match." in content
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_tools.py::test_write_report_shows_rationale -v`
Expected: FAIL — rationale not in report output

- [ ] **Step 3: Update write_report to include rationale**

In `agent/tools.py`, in the `write_report` function, add a `rationale` variable alongside `summary` and add it to the output. Replace the block starting at `summary      = listing.get("summary") or ""` through the end of the listing section:

```python
        summary      = listing.get("summary") or ""
        rationale    = listing.get("rationale") or ""
        url          = listing.get("url") or "#"

        lines.append(f"## #{i} — {title} @ {company}")
        lines.append(f"Score: {score}/100")
        if rationale:
            lines.append(f"Why: {rationale}")
        lines.append(f"Location: {location}")
        lines.append(f"Deadline: {deadline}")
        lines.append(f"Compensation: {compensation}")
        requirements = [r for r in requirements if r]
        if requirements:
            lines.append(f"Skills: {', '.join(requirements)}")
        eligibility = [e for e in (listing.get("eligibility") or []) if e]
        if eligibility:
            lines.append("Eligibility:")
            for constraint in eligibility:
                lines.append(f"  - {constraint}")
        lines.append("")
        if summary:
            lines.append(summary)
        lines.append("")
        lines.append(f"[View listing →]({url})")
        lines.append("")
        lines.append("---")
        lines.append("")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_tools.py::test_write_report_shows_rationale -v`
Expected: PASS

- [ ] **Step 5: Run full test suite**

Run: `pytest tests/test_tools.py -v`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add agent/tools.py tests/test_tools.py
git commit -m "feat: show scoring rationale in report"
```

---

### Task 5: Update agent.py to thread profile and preferences

**Files:**
- Modify: `agent/agent.py`

- [ ] **Step 1: Update `run()` signature, SYSTEM_PROMPT, and TOOL_MAP**

In `agent/agent.py`:

1. Replace the `SYSTEM_PROMPT` constant:

```python
SYSTEM_PROMPT = """You are an internship ranking agent.

You have raw internship listings to process. Use your tools in this order:
1. filter_expired — remove listings with past deadlines
2. fetch_descriptions — fetch the full description text from each listing's detail page
3. enrich_listings — extract compensation, deadline, location, and requirements from each description
4. score_listing — score all remaining listings for relevance
5. deduplicate — merge duplicate listings across sources
6. rank_listings — sort by score
7. write_report — write the final report (call this last)

Always call write_report when you are done. Do not stop before calling it."""
```

2. Update `run()` to accept `profile` and `preferences`, and update `TOOL_MAP` to capture them:

```python
def run(listings: list, profile: dict = None, preferences: dict = None):
    current = listings

    _profile = profile or {}
    _preferences = preferences or {}

    tool_map = {
        "filter_expired":     lambda args: tool_fns.filter_expired(args["listings"]),
        "fetch_descriptions": lambda args: tool_fns.fetch_descriptions(args["listings"]),
        "enrich_listings":    lambda args: tool_fns.enrich_listings(args["listings"]),
        "score_listing":      lambda args: tool_fns.score_listing(args["listings"], _profile, _preferences),
        "deduplicate":        lambda args: tool_fns.deduplicate(args["listings"]),
        "rank_listings":      lambda args: tool_fns.rank_listings(args["listings"]),
        "write_report":       lambda args: tool_fns.write_report(args["listings"]),
    }
```

3. Replace all references to `TOOL_MAP` inside the loop with `tool_map` (lowercase):

```python
            result = tool_map[name]({"listings": current})
```

Also remove the module-level `TOOL_MAP` dict entirely (lines 109–117), since it's now defined inside `run()`.

- [ ] **Step 2: Run tests to check for regressions**

Run: `pytest -v`
Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add agent/agent.py
git commit -m "feat: thread profile and preferences into score_listing via agent run()"
```

---

### Task 6: Update main.py to load preferences and profile

**Files:**
- Modify: `main.py`

- [ ] **Step 1: Update main() to validate preferences, load/generate profile, and pass to agent**

Replace the `main()` function in `main.py`:

```python
def main():
    import json
    parser = argparse.ArgumentParser(description="Internship Agent")
    parser.add_argument("--skip-scrape", action="store_true", help="Skip scraping and use existing data in data/raw/")
    args = parser.parse_args()

    preferences_path = BASE / "data" / "preferences.json"
    if not preferences_path.exists():
        raise FileNotFoundError(
            "No preferences.json found at data/preferences.json. "
            "Please create it with your target_role and location_preference."
        )
    with open(preferences_path) as f:
        preferences = json.load(f)

    from resume_parser import parse_resume
    profile = parse_resume(data_dir=BASE / "data")

    if not args.skip_scrape:
        run_scrapers()

    listings = load_raw_data()
    if not listings:
        logger.error("No listings found. Run without --skip-scrape or check scrapers.")
        sys.exit(1)

    logger.info(f"Running agent on {len(listings)} listings...")

    from agent.agent import run
    report_path = run(listings, profile=profile, preferences=preferences)

    if report_path:
        logger.info(f"Done! Report saved to: {report_path}")
    else:
        logger.error("Agent did not produce a report.")
        sys.exit(1)
```

- [ ] **Step 2: Create data/preferences.json for local use**

Create `data/preferences.json` (do not commit — add to .gitignore):

```json
{
  "target_role": "Software Engineering",
  "location_preference": "Cebu"
}
```

- [ ] **Step 3: Add data/preferences.json and data/profile.json to .gitignore**

Check if `.gitignore` exists. If so, add these lines:

```
data/preferences.json
data/profile.json
```

If `.gitignore` doesn't exist, create it with those two lines.

- [ ] **Step 4: Run full test suite**

Run: `pytest -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add main.py .gitignore
git commit -m "feat: load preferences and profile in main, pass to agent"
```

---

## Verification

After all tasks are complete, run a full end-to-end check:

```bash
# Confirm all tests pass
pytest -v

# Confirm the pipeline runs (requires data/resume.pdf or .docx and data/preferences.json)
python main.py --skip-scrape
```

Expected: Report generated at `output/report.md` with scores and rationales for each listing.
