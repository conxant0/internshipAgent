# Enrich Listings Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an `enrich_listings` tool that uses a small LLM to extract specific `compensation`, `deadline`, `location`, and `requirements` values from each listing's description, overwriting existing values with more specific ones.

**Architecture:** A new `enrich_listings(listings)` function in `agent/tools.py` calls `llm_client.chat()` once per listing with a small fast model, parses the JSON response, and overwrites fields where the LLM returned a non-null value. It is wired into the agent pipeline between `fetch_descriptions` and `score_listing`.

**Tech Stack:** Python, Groq API (`llama-3.1-8b-instant`), `unittest.mock` for tests.

---

## File Map

- Modify: `agent/llm_client.py` — add optional `model` parameter to `chat()`
- Modify: `agent/tools.py` — add `enrich_listings()` function
- Modify: `agent/agent.py` — wire `enrich_listings` into TOOLS, TOOL_MAP, SYSTEM_PROMPT
- Modify: `tests/test_tools.py` — add tests for `enrich_listings`

---

### Task 1: Add `model` parameter to `llm_client.chat()`

**Files:**
- Modify: `agent/llm_client.py`

- [ ] **Step 1: Write the failing test**

In `tests/test_tools.py`, find the existing line `from unittest.mock import patch` (near the bottom of the file) and replace it with:

```python
from unittest.mock import patch, MagicMock
from agent.llm_client import chat
```

Then add the test function below it:

def test_chat_uses_custom_model():
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_client.chat.completions.create.return_value = mock_response

    with patch("agent.llm_client.Groq", return_value=mock_client):
        chat([{"role": "user", "content": "hi"}], model="llama-3.1-8b-instant")

    call_kwargs = mock_client.chat.completions.create.call_args[1]
    assert call_kwargs["model"] == "llama-3.1-8b-instant"
```

- [ ] **Step 2: Run to verify it fails**

```bash
pytest tests/test_tools.py::test_chat_uses_custom_model -v
```

Expected: FAIL — `chat()` does not accept a `model` parameter yet.

- [ ] **Step 3: Update `agent/llm_client.py`**

Replace the current `chat()` function with:

```python
def chat(messages: list, tools: list = None, model: str = "llama-3.3-70b-versatile"):
    client = Groq(api_key=os.environ["GROQ_API_KEY"])
    kwargs = {
        "model": model,
        "messages": messages,
    }
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"

    response = client.chat.completions.create(**kwargs)
    return response.choices[0].message
```

- [ ] **Step 4: Run to verify it passes**

```bash
pytest tests/test_tools.py::test_chat_uses_custom_model -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add agent/llm_client.py tests/test_tools.py
git commit -m "feat: add model param to llm_client.chat"
```

---

### Task 2: Add `enrich_listings()` to `agent/tools.py`

**Files:**
- Modify: `agent/tools.py`
- Modify: `tests/test_tools.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_tools.py` (after the Task 1 test, no new imports needed):

```python
from agent.tools import enrich_listings

ENRICH_DESCRIPTION = "Stipend: PHP 9000/month. Applications close 2026-07-31. Based in Cebu City. Must know Python and FastAPI."

def _mock_llm_response(content: str):
    msg = MagicMock()
    msg.content = content
    return msg

def test_enrich_overwrites_compensation():
    listing = make_listing(description=ENRICH_DESCRIPTION, compensation="Paid")
    with patch("agent.tools.chat", return_value=_mock_llm_response(
        '{"compensation": "PHP 9000/month", "deadline": null, "location": null, "requirements": null}'
    )):
        result = enrich_listings([listing])
    assert result[0]["compensation"] == "PHP 9000/month"

def test_enrich_overwrites_deadline():
    listing = make_listing(description=ENRICH_DESCRIPTION, deadline=None)
    with patch("agent.tools.chat", return_value=_mock_llm_response(
        '{"compensation": null, "deadline": "2026-07-31", "location": null, "requirements": null}'
    )):
        result = enrich_listings([listing])
    assert result[0]["deadline"] == "2026-07-31"

def test_enrich_overwrites_requirements():
    listing = make_listing(description=ENRICH_DESCRIPTION, requirements=["IT & Computer Science"])
    with patch("agent.tools.chat", return_value=_mock_llm_response(
        '{"compensation": null, "deadline": null, "location": null, "requirements": ["Python", "FastAPI"]}'
    )):
        result = enrich_listings([listing])
    assert result[0]["requirements"] == ["Python", "FastAPI"]

def test_enrich_leaves_field_unchanged_when_null():
    listing = make_listing(description=ENRICH_DESCRIPTION, compensation="Paid — PHP 5000/monthly")
    with patch("agent.tools.chat", return_value=_mock_llm_response(
        '{"compensation": null, "deadline": null, "location": null, "requirements": null}'
    )):
        result = enrich_listings([listing])
    assert result[0]["compensation"] == "Paid — PHP 5000/monthly"

def test_enrich_skips_empty_description():
    listing = make_listing(description="")
    called = []
    with patch("agent.tools.chat", side_effect=lambda *a, **kw: called.append(1)):
        enrich_listings([listing])
    assert len(called) == 0

def test_enrich_continues_on_llm_error():
    listings = [
        make_listing(description="desc one", url="https://example.com/1"),
        make_listing(description="desc two", url="https://example.com/2", compensation=None),
    ]
    call_count = [0]
    def side_effect(*args, **kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            raise Exception("LLM error")
        return _mock_llm_response('{"compensation": "PHP 5000/month", "deadline": null, "location": null, "requirements": null}')

    with patch("agent.tools.chat", side_effect=side_effect):
        result = enrich_listings(listings)

    assert result[1]["compensation"] == "PHP 5000/month"

def test_enrich_continues_on_bad_json():
    listing = make_listing(description="Some description here.")
    with patch("agent.tools.chat", return_value=_mock_llm_response("not valid json")):
        result = enrich_listings([listing])
    assert result[0]["compensation"] == "Paid"  # unchanged from make_listing default
```

- [ ] **Step 2: Run to verify they fail**

```bash
pytest tests/test_tools.py -k "enrich" -v
```

Expected: FAIL — `enrich_listings` not defined.

- [ ] **Step 3: Add `enrich_listings` to `agent/tools.py`**

Add this import at the top of `agent/tools.py`:

```python
from agent.llm_client import chat
```

Add this constant after the existing `DESCRIPTION_FETCHERS` block:

```python
_ENRICH_MODEL = "llama-3.1-8b-instant"

_ENRICH_PROMPT = """Extract the following fields from this job description. Return ONLY a JSON object.
If a field is not mentioned, return null for that key.

Fields:
- compensation: string (e.g. "PHP 8000/month") or null
- deadline: string in YYYY-MM-DD format or null
- location: string (e.g. "Cebu City, Philippines") or null
- requirements: list of specific skills (e.g. ["Python", "React", "SQL"]) or null

Description:
{description}"""
```

Add this function after `fetch_descriptions`:

```python
def enrich_listings(listings: List[dict]) -> List[dict]:
    """Use a small LLM to extract structured fields from each listing's description."""
    import json as _json
    for listing in listings:
        description = listing.get("description") or ""
        if not description:
            continue
        try:
            response = chat(
                [{"role": "user", "content": _ENRICH_PROMPT.format(description=description)}],
                model=_ENRICH_MODEL,
            )
            extracted = _json.loads(response.content)
            for field in ("compensation", "deadline", "location", "requirements"):
                if extracted.get(field) is not None:
                    listing[field] = extracted[field]
        except Exception as e:
            logger.warning(f"enrich_listings failed for {listing.get('url')}: {e}")
    return listings
```

- [ ] **Step 4: Run to verify tests pass**

```bash
pytest tests/test_tools.py -k "enrich" -v
```

Expected: all 7 tests PASS

- [ ] **Step 5: Run full test suite to check for regressions**

```bash
pytest tests/test_tools.py -v
```

Expected: all tests PASS

- [ ] **Step 6: Commit**

```bash
git add agent/tools.py tests/test_tools.py
git commit -m "feat: add enrich_listings tool"
```

---

### Task 3: Wire `enrich_listings` into the agent pipeline

**Files:**
- Modify: `agent/agent.py`

- [ ] **Step 1: Update `SYSTEM_PROMPT` in `agent/agent.py`**

Replace the numbered tool list in `SYSTEM_PROMPT` with:

```python
SYSTEM_PROMPT = """You are an internship ranking agent for a 3rd year CS student based in Cebu, Philippines.
Their skills: Python, Django, React, AWS, Docker.

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

- [ ] **Step 2: Add `enrich_listings` to the `TOOLS` list**

Add this entry to the `TOOLS` list in `agent/agent.py`, after the `fetch_descriptions` entry:

```python
{
    "type": "function",
    "function": {
        "name": "enrich_listings",
        "description": "Use a small LLM to extract compensation, deadline, location, and specific skill requirements from each listing's description. Overwrites existing fields with more specific values. Call this after fetch_descriptions and before score_listing.",
        "parameters": {
            "type": "object",
            "properties": {"listings": {"type": "array", "items": {"type": "object"}}},
            "required": ["listings"],
        },
    },
},
```

- [ ] **Step 3: Add `enrich_listings` to `TOOL_MAP`**

Add this entry to `TOOL_MAP` in `agent/agent.py`, after the `fetch_descriptions` entry:

```python
"enrich_listings": lambda args: tool_fns.enrich_listings(args["listings"]),
```

- [ ] **Step 4: Update the user message tool order**

In `agent/agent.py`, find the `content` string in the initial user message and update the tool order:

```python
f"Call tools in order: filter_expired → fetch_descriptions → enrich_listings → score_listing → deduplicate → rank_listings → write_report.\n\n"
```

- [ ] **Step 5: Run the full test suite**

```bash
pytest -v
```

Expected: all tests PASS

- [ ] **Step 6: Commit**

```bash
git add agent/agent.py
git commit -m "feat: wire enrich_listings into agent pipeline"
```
