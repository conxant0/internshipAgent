# Eligibility Parsing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an `eligibility` field (list of plain strings) extracted from listing descriptions by the existing LLM enrichment step, and display it in the report.

**Architecture:** Extend `_ENRICH_PROMPT` with an `eligibility` field, add `"eligibility"` to the field-copy loop in `enrich_listings`, and render it in `write_report`. No new tools, no new pipeline steps, no new LLM calls.

**Tech Stack:** Python, pytest, existing Groq LLM client (`llama-3.1-8b-instant`)

---

### Task 1: Add eligibility extraction to enrich prompt and copy loop

**Files:**
- Modify: `agent/tools.py`
- Test: `tests/test_tools.py`

- [ ] **Step 1: Write the failing tests**

Add these tests to the bottom of `tests/test_tools.py`:

```python
def test_enrich_extracts_eligibility():
    listing = make_listing(description="Must be a 3rd year CS student. 480 hours required. Voluntary internship only.")
    with patch("agent.tools.chat", return_value=_mock_llm_response(
        '{"compensation": null, "deadline": null, "location": null, "requirements": null, "summary": null, "eligibility": ["3rd year CS students only", "480 hours required", "voluntary internship only"]}'
    )):
        result = enrich_listings([listing])
    assert result[0]["eligibility"] == ["3rd year CS students only", "480 hours required", "voluntary internship only"]

def test_enrich_leaves_eligibility_absent_when_null():
    listing = make_listing(description="Join our team as a software intern.")
    with patch("agent.tools.chat", return_value=_mock_llm_response(
        '{"compensation": null, "deadline": null, "location": null, "requirements": null, "summary": null, "eligibility": null}'
    )):
        result = enrich_listings([listing])
    assert "eligibility" not in result[0]
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest tests/test_tools.py::test_enrich_extracts_eligibility tests/test_tools.py::test_enrich_leaves_eligibility_absent_when_null -v
```

Expected: both FAIL — `eligibility` key missing from result.

- [ ] **Step 3: Add `eligibility` to `_ENRICH_PROMPT` in `agent/tools.py`**

In `_ENRICH_PROMPT`, after the `requirements` line, add:

```python
_ENRICH_PROMPT = """Extract the following fields from this job description. Return ONLY a JSON object.
If a field is not mentioned, return null for that key.

Fields:
- compensation: string including amount and frequency if mentioned (e.g. "PHP 8000/month", "PHP 500/day", "PHP 2000/week", "PHP 10000 upon completion"). Include the frequency (monthly, weekly, daily, upon completion) when stated. or null
- deadline: string in YYYY-MM-DD format or null
- location: string (e.g. "Cebu City, Philippines") or null
- summary: 1-2 sentence plain description of what the intern will actually do in the role. Focus on responsibilities only. Do not mention skills, tools, compensation, or requirements — those are captured separately. No filler phrases like "join our team" or "exciting opportunity". Return null if unclear.
- requirements: list of SPECIFIC technical skills only — tools, software, programming languages, platforms (e.g. ["Python", "React", "SQL", "MS Office"]). EXCLUDE soft skills (communication, teamwork), personality traits, degree requirements, industry interests, or anything that is not a concrete technical skill or tool. Return null if none found.
- eligibility: list of plain-English eligibility constraints — year level required (e.g. "3rd year students only"), hours to render (e.g. "480 hours required"), internship type (e.g. "voluntary internship only", "academic internship only", "for-credit internship"), course restrictions (e.g. "BS Computer Science only"), citizenship requirements. Each item is a short phrase. Return null if none found.

Description:
{description}"""
```

- [ ] **Step 4: Add `"eligibility"` to the field-copy loop in `enrich_listings`**

In `agent/tools.py`, find this line:

```python
for field in ("compensation", "deadline", "location", "requirements", "summary"):
```

Change it to:

```python
for field in ("compensation", "deadline", "location", "requirements", "summary", "eligibility"):
```

- [ ] **Step 5: Run tests to confirm they pass**

```bash
pytest tests/test_tools.py::test_enrich_extracts_eligibility tests/test_tools.py::test_enrich_leaves_eligibility_absent_when_null -v
```

Expected: both PASS.

- [ ] **Step 6: Run the full test suite to check for regressions**

```bash
pytest
```

Expected: all tests PASS.

- [ ] **Step 7: Commit**

```bash
git add agent/tools.py tests/test_tools.py
git commit -m "feat: extract eligibility constraints in enrich_listings"
```

---

### Task 2: Display eligibility in the report

**Files:**
- Modify: `agent/tools.py` (`write_report`)
- Test: `tests/test_tools.py`

- [ ] **Step 1: Write the failing tests**

Add these tests to the bottom of `tests/test_tools.py`:

```python
def test_write_report_shows_eligibility(tmp_path):
    listing = make_listing(score=80, eligibility=["3rd year CS students only", "480 hours required"])
    output_file = str(tmp_path / "report.md")
    write_report([listing], output_path=output_file)
    content = open(output_file).read()
    assert "Eligibility:" in content
    assert "3rd year CS students only" in content
    assert "480 hours required" in content

def test_write_report_omits_eligibility_when_absent(tmp_path):
    listing = make_listing(score=80)  # no eligibility key
    output_file = str(tmp_path / "report.md")
    write_report([listing], output_path=output_file)
    content = open(output_file).read()
    assert "Eligibility:" not in content
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest tests/test_tools.py::test_write_report_shows_eligibility tests/test_tools.py::test_write_report_omits_eligibility_when_absent -v
```

Expected: both FAIL — "Eligibility:" not in report output.

- [ ] **Step 3: Add eligibility line to `write_report` in `agent/tools.py`**

In `write_report`, find this block:

```python
        if requirements:
            lines.append(f"Skills: {', '.join(requirements)}")
```

Replace it with:

```python
        if requirements:
            lines.append(f"Skills: {', '.join(requirements)}")
        eligibility = listing.get("eligibility") or []
        if eligibility:
            lines.append(f"Eligibility: {', '.join(eligibility)}")
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
pytest tests/test_tools.py::test_write_report_shows_eligibility tests/test_tools.py::test_write_report_omits_eligibility_when_absent -v
```

Expected: both PASS.

- [ ] **Step 5: Run the full test suite to check for regressions**

```bash
pytest
```

Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add agent/tools.py tests/test_tools.py
git commit -m "feat: display eligibility constraints in report"
```
