# Resume Checkpoints Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `--resume` flag to `main.py` so a failed pipeline run can restart from the last completed stage instead of from scratch.

**Architecture:** After each tool completes in the agent loop, serialize `current` listings to `data/checkpoints/<stage>.json`. When `run()` is called with `resume=True`, find the latest checkpoint, load it as the starting state, and wrap already-completed tools as no-ops so the LLM still drives the loop but skipped stages return immediately without re-running.

**Tech Stack:** Python stdlib only (`json`, `pathlib`). No new dependencies.

---

## File Map

| File | Change |
|------|--------|
| `agent/agent.py` | Add `STAGE_ORDER`, `_save_checkpoint`, `_load_latest_checkpoint`; add `resume` param to `run()`; save checkpoint after each stage; skip completed stages on resume |
| `main.py` | Add `--resume` argparse flag; pass `resume=args.resume` to `run()` |
| `tests/test_agent.py` | Add tests for checkpoint save, checkpoint load/skip, and no-checkpoint fallback |

---

### Task 1: Add checkpoint helpers and `STAGE_ORDER` to `agent/agent.py`

**Files:**
- Modify: `agent/agent.py`

- [ ] **Step 1: Write the failing test**

```python
# In tests/test_agent.py — add at bottom

import tempfile
from pathlib import Path
from unittest.mock import patch

def test_save_checkpoint_creates_file(tmp_path):
    with patch("agent.agent._CHECKPOINT_DIR", tmp_path):
        from agent.agent import _save_checkpoint
        _save_checkpoint("filter_expired", [{"title": "A"}])
    assert (tmp_path / "filter_expired.json").exists()

def test_load_latest_checkpoint_returns_none_when_empty(tmp_path):
    with patch("agent.agent._CHECKPOINT_DIR", tmp_path):
        from agent.agent import _load_latest_checkpoint
        stage, listings = _load_latest_checkpoint()
    assert stage is None
    assert listings is None

def test_load_latest_checkpoint_returns_last_stage(tmp_path):
    import json
    (tmp_path / "filter_expired.json").write_text(json.dumps([{"title": "A"}]))
    (tmp_path / "enrich_listings.json").write_text(json.dumps([{"title": "B"}]))
    with patch("agent.agent._CHECKPOINT_DIR", tmp_path):
        from agent.agent import _load_latest_checkpoint, STAGE_ORDER
        stage, listings = _load_latest_checkpoint()
    # enrich_listings comes after filter_expired in STAGE_ORDER, so it's "latest"
    assert stage == "enrich_listings"
    assert listings == [{"title": "B"}]
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
pytest tests/test_agent.py::test_save_checkpoint_creates_file tests/test_agent.py::test_load_latest_checkpoint_returns_none_when_empty tests/test_agent.py::test_load_latest_checkpoint_returns_last_stage -v
```

Expected: FAIL with `ImportError` or `AttributeError` (functions don't exist yet)

- [ ] **Step 3: Add `STAGE_ORDER`, `_CHECKPOINT_DIR`, `_save_checkpoint`, `_load_latest_checkpoint` to `agent/agent.py`**

Add after the imports at the top of `agent/agent.py` (before `SYSTEM_PROMPT`):

```python
from pathlib import Path

STAGE_ORDER = [
    "filter_expired",
    "fetch_descriptions",
    "enrich_listings",
    "filter_ineligible",
    "score_listing",
    "deduplicate",
    "rank_listings",
]

_CHECKPOINT_DIR = Path(__file__).parent.parent / "data" / "checkpoints"


def _save_checkpoint(stage: str, listings: list) -> None:
    _CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    with open(_CHECKPOINT_DIR / f"{stage}.json", "w", encoding="utf-8") as f:
        json.dump(listings, f, indent=2)


def _load_latest_checkpoint() -> tuple:
    """Return (last_completed_stage, listings) or (None, None)."""
    for stage in reversed(STAGE_ORDER):
        path = _CHECKPOINT_DIR / f"{stage}.json"
        if path.exists():
            with open(path, encoding="utf-8") as f:
                return stage, json.load(f)
    return None, None
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_agent.py::test_save_checkpoint_creates_file tests/test_agent.py::test_load_latest_checkpoint_returns_none_when_empty tests/test_agent.py::test_load_latest_checkpoint_returns_last_stage -v
```

Expected: all 3 PASS

- [ ] **Step 5: Commit**

```bash
git add agent/agent.py tests/test_agent.py
git commit -m "feat: add checkpoint helpers and STAGE_ORDER to agent"
```

---

### Task 2: Save checkpoint after each stage in the agent loop

**Files:**
- Modify: `agent/agent.py` (the `run()` function's tool execution block)

- [ ] **Step 1: Write the failing test**

```python
# In tests/test_agent.py — add at bottom

def test_run_saves_checkpoint_after_each_stage(tmp_path):
    import json

    responses = [
        make_response(tool_calls=[make_tool_call("filter_expired", {})]),
        make_response(tool_calls=[make_tool_call("write_report", {})]),
    ]

    output_file = str(tmp_path / "report.md")
    with patch("agent.agent.chat", side_effect=responses), \
         patch("agent.agent.tool_fns.filter_expired", return_value=SAMPLE_LISTINGS), \
         patch("agent.agent.tool_fns.write_report", return_value=output_file), \
         patch("agent.agent._CHECKPOINT_DIR", tmp_path):
        from agent.agent import run
        run(SAMPLE_LISTINGS)

    assert (tmp_path / "filter_expired.json").exists()
    saved = json.loads((tmp_path / "filter_expired.json").read_text())
    assert saved == SAMPLE_LISTINGS
```

- [ ] **Step 2: Run to verify it fails**

```bash
pytest tests/test_agent.py::test_run_saves_checkpoint_after_each_stage -v
```

Expected: FAIL — checkpoint file not created

- [ ] **Step 3: Add checkpoint save in the agent loop**

In `agent/agent.py`, find the block inside `run()` that appends the tool result to messages (after `current = result`). Add `_save_checkpoint` call:

```python
            current = result
            if name in STAGE_ORDER:
                _save_checkpoint(name, current)
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": f"Done. {len(current)} listings remaining.",
            })
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_agent.py::test_run_saves_checkpoint_after_each_stage -v
```

Expected: PASS

- [ ] **Step 5: Run the full test suite to check for regressions**

```bash
pytest tests/test_agent.py -v
```

Expected: all existing tests still pass

- [ ] **Step 6: Commit**

```bash
git add agent/agent.py tests/test_agent.py
git commit -m "feat: save checkpoint to data/checkpoints/<stage>.json after each agent stage"
```

---

### Task 3: Add `resume` param to `run()` — load checkpoint and skip completed stages

**Files:**
- Modify: `agent/agent.py` (the `run()` signature and body)

- [ ] **Step 1: Write the failing test**

```python
# In tests/test_agent.py — add at bottom

def test_run_resumes_from_checkpoint_skips_completed_stage(tmp_path):
    import json

    # Simulate a checkpoint where filter_expired already ran
    (tmp_path / "filter_expired.json").write_text(json.dumps(SAMPLE_LISTINGS))

    responses = [
        make_response(tool_calls=[make_tool_call("filter_expired", {})]),
        make_response(tool_calls=[make_tool_call("write_report", {})]),
    ]

    output_file = str(tmp_path / "report.md")
    filter_mock = MagicMock(return_value=SAMPLE_LISTINGS)

    with patch("agent.agent.chat", side_effect=responses), \
         patch("agent.agent.tool_fns.filter_expired", filter_mock), \
         patch("agent.agent.tool_fns.write_report", return_value=output_file), \
         patch("agent.agent._CHECKPOINT_DIR", tmp_path):
        from agent.agent import run
        result = run(SAMPLE_LISTINGS, resume=True)

    # filter_expired should NOT have been called — it was skipped via checkpoint
    filter_mock.assert_not_called()
    assert result == output_file


def test_run_resume_with_no_checkpoint_falls_back_to_normal(tmp_path):
    responses = [
        make_response(tool_calls=[make_tool_call("filter_expired", {})]),
        make_response(tool_calls=[make_tool_call("write_report", {})]),
    ]

    output_file = str(tmp_path / "report.md")
    filter_mock = MagicMock(return_value=SAMPLE_LISTINGS)

    with patch("agent.agent.chat", side_effect=responses), \
         patch("agent.agent.tool_fns.filter_expired", filter_mock), \
         patch("agent.agent.tool_fns.write_report", return_value=output_file), \
         patch("agent.agent._CHECKPOINT_DIR", tmp_path):
        from agent.agent import run
        result = run(SAMPLE_LISTINGS, resume=True)

    # No checkpoint → filter_expired ran normally
    filter_mock.assert_called_once()
    assert result == output_file
```

- [ ] **Step 2: Run to verify they fail**

```bash
pytest tests/test_agent.py::test_run_resumes_from_checkpoint_skips_completed_stage tests/test_agent.py::test_run_resume_with_no_checkpoint_falls_back_to_normal -v
```

Expected: FAIL — `run()` doesn't accept `resume` param yet

- [ ] **Step 3: Add `resume` logic to `run()`**

Change the signature and add resume logic at the top of `run()` in `agent/agent.py`:

```python
def run(listings: list, profile: dict = None, preferences: dict = None, resume: bool = False):
    current = listings
    completed_stages: set = set()

    if resume:
        last_stage, saved = _load_latest_checkpoint()
        if last_stage:
            current = saved
            completed_stages = set(STAGE_ORDER[: STAGE_ORDER.index(last_stage) + 1])
            logger.info(f"Resuming from checkpoint after '{last_stage}' ({len(current)} listings)")
```

Then after `tool_map` is defined, add the no-op wrappers for completed stages:

```python
    for stage in completed_stages:
        if stage in tool_map:
            _stage = stage  # capture for closure
            tool_map[_stage] = lambda lst, s=_stage: (
                logger.info(f"Skipping '{s}' — already completed (checkpoint)") or lst
            )
```

Full updated `run()` signature block (replace existing):

```python
def run(listings: list, profile: dict = None, preferences: dict = None, resume: bool = False):
    current = listings
    completed_stages: set = set()

    if resume:
        last_stage, saved = _load_latest_checkpoint()
        if last_stage:
            current = saved
            completed_stages = set(STAGE_ORDER[: STAGE_ORDER.index(last_stage) + 1])
            logger.info(f"Resuming from checkpoint after '{last_stage}' ({len(current)} listings)")

    _profile = profile or {}
    _preferences = preferences or {}

    tool_map = {
        "filter_expired":     lambda lst: tool_fns.filter_expired(lst),
        "fetch_descriptions": lambda lst: tool_fns.fetch_descriptions(lst),
        "enrich_listings":    lambda lst: tool_fns.enrich_listings(lst),
        "filter_ineligible":  lambda lst: tool_fns.filter_ineligible(lst),
        "score_listing":      lambda lst: tool_fns.score_listing(lst, _profile, _preferences),
        "deduplicate":        lambda lst: tool_fns.deduplicate(lst),
        "rank_listings":      lambda lst: tool_fns.rank_listings(lst),
        "write_report":       lambda lst: tool_fns.write_report(lst),
    }

    for stage in completed_stages:
        if stage in tool_map:
            tool_map[stage] = lambda lst, s=stage: (
                logger.info(f"Skipping '{s}' — already completed (checkpoint)") or lst
            )
    # ... rest of function unchanged
```

- [ ] **Step 4: Run new tests to verify they pass**

```bash
pytest tests/test_agent.py::test_run_resumes_from_checkpoint_skips_completed_stage tests/test_agent.py::test_run_resume_with_no_checkpoint_falls_back_to_normal -v
```

Expected: both PASS

- [ ] **Step 5: Run the full test suite**

```bash
pytest tests/test_agent.py -v
```

Expected: all tests pass

- [ ] **Step 6: Commit**

```bash
git add agent/agent.py tests/test_agent.py
git commit -m "feat: add resume param to run() — load checkpoint and skip completed stages"
```

---

### Task 4: Add `--resume` flag to `main.py`

**Files:**
- Modify: `main.py`

- [ ] **Step 1: Add the argparse flag**

In `main.py`, find the existing `--skip-scrape` argument and add `--resume` right after it:

```python
    parser.add_argument("--skip-scrape", action="store_true", help="Skip scraping and use existing data in data/raw/")
    parser.add_argument("--resume", action="store_true", help="Resume from last checkpoint instead of reprocessing from scratch")
```

- [ ] **Step 2: Pass `resume` to `run()`**

Find the `run(listings, ...)` call and add the flag:

```python
    report_path = run(listings, profile=profile, preferences=preferences, resume=args.resume)
```

- [ ] **Step 3: Verify the flag is wired up**

```bash
python main.py --help
```

Expected output includes:
```
  --resume    Resume from last checkpoint instead of reprocessing from scratch
```

- [ ] **Step 4: Run the full test suite one final time**

```bash
pytest -v
```

Expected: all tests pass

- [ ] **Step 5: Commit**

```bash
git add main.py
git commit -m "feat: add --resume flag to main.py"
```
