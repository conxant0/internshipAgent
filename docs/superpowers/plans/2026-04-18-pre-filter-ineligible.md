# Pre-Filter Ineligible Listings Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `filter_ineligible` tool that runs after `enrich_listings` and drops listings with (a) past deadlines now visible post-enrichment, and (b) eligibility constraints that restrict to a non-CS/IT field — reducing LLM calls in `score_listing`.

**Architecture:** A new pure-Python function `filter_ineligible(listings)` is added to `agent/tools.py`. It re-checks deadlines (enrichment may have populated previously-null deadlines) and scans each listing's `eligibility` list against a hardcoded CS/IT whitelist: if an eligibility constraint names a course family that is not CS, IT, engineering, or STEM, the listing is dropped. No profile parameter — the whitelist is fixed. The function is registered as a tool in `agent/agent.py` and inserted into the pipeline between `enrich_listings` and `score_listing`.

**Tech Stack:** Python stdlib only — `datetime`. No LLM calls.

---

## File Map

- Modify: `agent/tools.py` — add `filter_ineligible` function
- Modify: `agent/agent.py` — add tool definition, tool_map entry, update system prompt
- Modify: `tests/test_tools.py` — add tests for `filter_ineligible`

---

### Task 1: Write failing tests for `filter_ineligible`

**Files:**
- Modify: `tests/test_tools.py`

- [ ] **Step 1: Write the failing tests**

Add these tests at the bottom of `tests/test_tools.py`, after the `enrich_listings` section:

```python
# ── filter_ineligible ─────────────────────────────────────────────────────────

from agent.tools import filter_ineligible

def test_filter_ineligible_keeps_no_eligibility():
    listing = make_listing(eligibility=None)
    result = filter_ineligible([listing])
    assert len(result) == 1

def test_filter_ineligible_keeps_cs_restriction():
    listing = make_listing(eligibility=["BS Computer Science only"])
    result = filter_ineligible([listing])
    assert len(result) == 1

def test_filter_ineligible_keeps_it_restriction():
    listing = make_listing(eligibility=["BS Information Technology or BS Computer Science only"])
    result = filter_ineligible([listing])
    assert len(result) == 1

def test_filter_ineligible_keeps_stem_restriction():
    listing = make_listing(eligibility=["STEM students only"])
    result = filter_ineligible([listing])
    assert len(result) == 1

def test_filter_ineligible_keeps_engineering_restriction():
    listing = make_listing(eligibility=["Engineering students only"])
    result = filter_ineligible([listing])
    assert len(result) == 1

def test_filter_ineligible_keeps_open_to_all():
    listing = make_listing(eligibility=["open to all courses", "480 hours required"])
    result = filter_ineligible([listing])
    assert len(result) == 1

def test_filter_ineligible_keeps_non_course_constraints():
    listing = make_listing(eligibility=["480 hours required", "voluntary internship only"])
    result = filter_ineligible([listing])
    assert len(result) == 1

def test_filter_ineligible_drops_nursing_only():
    listing = make_listing(eligibility=["Nursing students only"])
    result = filter_ineligible([listing])
    assert len(result) == 0

def test_filter_ineligible_drops_law_only():
    listing = make_listing(eligibility=["Law students only"])
    result = filter_ineligible([listing])
    assert len(result) == 0

def test_filter_ineligible_drops_accountancy_only():
    listing = make_listing(eligibility=["Accountancy students only"])
    result = filter_ineligible([listing])
    assert len(result) == 0

def test_filter_ineligible_drops_non_cs_with_other_constraints():
    listing = make_listing(eligibility=["Nursing students only", "480 hours required"])
    result = filter_ineligible([listing])
    assert len(result) == 0

def test_filter_ineligible_keeps_mixed_cs_and_non_cs():
    # "IT or Nursing" — CS signal present, so benefit of the doubt
    listing = make_listing(eligibility=["IT or Nursing students welcome"])
    result = filter_ineligible([listing])
    assert len(result) == 1

def test_filter_ineligible_drops_post_enrichment_expired_deadline():
    listing = make_listing(deadline="2000-01-01")
    result = filter_ineligible([listing])
    assert len(result) == 0

def test_filter_ineligible_keeps_future_deadline():
    listing = make_listing(deadline="2099-12-31")
    result = filter_ineligible([listing])
    assert len(result) == 1

def test_filter_ineligible_keeps_null_deadline():
    listing = make_listing(deadline=None)
    result = filter_ineligible([listing])
    assert len(result) == 1

def test_filter_ineligible_empty_list():
    result = filter_ineligible([])
    assert result == []

def test_filter_ineligible_mixed_batch():
    listings = [
        make_listing(title="CS Intern", eligibility=["BS Computer Science only"]),
        make_listing(title="Nursing Intern", eligibility=["Nursing students only"]),
        make_listing(title="Open Intern", eligibility=None),
        make_listing(title="Expired Intern", deadline="2000-01-01"),
    ]
    result = filter_ineligible(listings)
    assert len(result) == 2
    titles = {r["title"] for r in result}
    assert titles == {"CS Intern", "Open Intern"}
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_tools.py -k "filter_ineligible" -v
```

Expected: `ImportError` or `FAILED` — `filter_ineligible` does not exist yet.

---

### Task 2: Implement `filter_ineligible` in `agent/tools.py`

**Files:**
- Modify: `agent/tools.py`

- [ ] **Step 1: Add the function after `filter_expired`**

Insert the following block in `agent/tools.py` after the `filter_expired` function (after line 73):

```python
# Eligibility strings containing any of these are compatible with CS/IT students.
# If a CS-compatible keyword is found, the listing is always kept.
_CS_IT_KEYWORDS = [
    "computer",
    "information technology",
    "software",
    "engineering",
    "stem",
    "technology",
    "data science",
    "all course",
    "any course",
    "open to all",
]

# Eligibility strings containing any of these name a non-CS/IT course family.
# A listing is dropped only when one of these is found AND no CS-compatible
# keyword is present in the same eligibility block.
_NON_CS_IT_KEYWORDS = [
    "nurs",
    "law ",
    " law",
    "medic",
    "dental",
    "pharmac",
    "fine art",
    "criminolog",
    "journali",
    "psycholog",
    "social work",
    "accountanc",
    "hotel",
    "tourism",
    "culinar",
    "agricultur",
    "veterinar",
    "education major",
    "teacher education",
    "liberal arts",
]


def _eligibility_excludes_cs_it(eligibility: list[str]) -> bool:
    """Return True when eligibility clearly restricts to a non-CS/IT field.

    Returns False (keep) when no non-CS keyword is found, or when a CS/IT
    keyword co-occurs (benefit of the doubt for mixed-field listings).
    """
    joined = " " + " ".join(eligibility).lower() + " "
    if any(kw in joined for kw in _CS_IT_KEYWORDS):
        return False
    return any(kw in joined for kw in _NON_CS_IT_KEYWORDS)


def filter_ineligible(listings: list[dict]) -> list[dict]:
    """Drop listings with post-enrichment expired deadlines or eligibility
    constraints that restrict to a non-CS/IT course field."""
    today = date.today().isoformat()
    result = []
    for listing in listings:
        deadline = listing.get("deadline")
        if deadline is not None and deadline < today:
            logger.info(
                f"filter_ineligible: dropping expired '{listing.get('title')}' (deadline {deadline})"
            )
            continue

        eligibility = listing.get("eligibility") or []
        if eligibility and _eligibility_excludes_cs_it(eligibility):
            logger.info(
                f"filter_ineligible: dropping non-CS/IT '{listing.get('title')}' (eligibility: {eligibility})"
            )
            continue

        result.append(listing)
    return result
```

- [ ] **Step 2: Run the tests to verify they pass**

```bash
pytest tests/test_tools.py -k "filter_ineligible" -v
```

Expected: all 17 tests pass.

- [ ] **Step 3: Commit**

```bash
git add agent/tools.py tests/test_tools.py
git commit -m "feat: add filter_ineligible — drops post-enrichment expired and non-CS/IT listings"
```

---

### Task 3: Register `filter_ineligible` in `agent/agent.py`

**Files:**
- Modify: `agent/agent.py`

- [ ] **Step 1: Update the system prompt**

In `agent/agent.py`, replace the `SYSTEM_PROMPT` string:

```python
SYSTEM_PROMPT = """You are an internship ranking agent.

You have raw internship listings to process. Use your tools in this order:
1. filter_expired — remove listings with past deadlines (raw scraped data)
2. fetch_descriptions — fetch the full description text from each listing's detail page
3. enrich_listings — extract compensation, deadline, location, and requirements from each description
4. filter_ineligible — drop listings with post-enrichment expired deadlines or non-CS/IT course restrictions
5. score_listing — score all remaining listings for relevance
6. deduplicate — merge duplicate listings across sources
7. rank_listings — sort by score
8. write_report — write the final report (call this last)

Always call write_report when you are done. Do not stop before calling it."""
```

- [ ] **Step 2: Add the tool definition to the TOOLS list**

In `agent/agent.py`, insert the following tool dict into the `TOOLS` list, after the `enrich_listings` entry and before the `score_listing` entry:

```python
    {
        "type": "function",
        "function": {
            "name": "filter_ineligible",
            "description": "Drop listings with post-enrichment expired deadlines or eligibility constraints that restrict to a non-CS/IT course field. Call this after enrich_listings and before score_listing.",
            "parameters": {
                "type": "object",
                "properties": {"listings": {"type": "array", "items": {"type": "object"}}},
                "required": ["listings"],
            },
        },
    },
```

- [ ] **Step 3: Add the tool to the tool_map**

In `agent/agent.py`, inside the `run()` function's `tool_map` dict, add the `filter_ineligible` entry after `enrich_listings`:

```python
"filter_ineligible": lambda args: tool_fns.filter_ineligible(args["listings"]),
```

- [ ] **Step 4: Update the user message**

In `agent/agent.py`, update the `content` string in the user message to reflect the new step order:

```python
f"Call tools in order: filter_expired → fetch_descriptions → enrich_listings → filter_ineligible → score_listing → deduplicate → rank_listings → write_report.\n\n"
```

- [ ] **Step 5: Run the full test suite**

```bash
pytest -v
```

Expected: all existing tests pass. No new failures.

- [ ] **Step 6: Commit**

```bash
git add agent/agent.py
git commit -m "feat: register filter_ineligible in agent pipeline"
```

---

## Self-Review

**Spec coverage:**
- Deadline re-check post-enrichment → Task 2 (`filter_ineligible` deadline check)
- Non-CS/IT course restriction drop → Task 2 (`_eligibility_excludes_cs_it` with whitelist + blocklist)
- CS/IT signal wins over non-CS when both present → Task 1 `test_filter_ineligible_keeps_mixed_cs_and_non_cs`, Task 2 early-return on CS keyword
- Pipeline wiring → Task 3

**Placeholder scan:** No TBDs, no "similar to above", all code is complete.

**Type consistency:** `filter_ineligible(listings: list[dict])` — no `profile` parameter. Used identically in `tools.py` (definition) and `agent.py` (lambda `tool_fns.filter_ineligible(args["listings"])`). `_eligibility_excludes_cs_it` is a private helper, not exposed in any tool schema.

**Edge cases covered:**
- `eligibility=None` → kept
- Non-course constraints only (hours, internship type) → kept
- Mixed CS + non-CS in one eligibility block → kept (CS signal wins)
- Deadline `None` → kept
- Past deadline post-enrichment → dropped
- Empty list → returns empty list
