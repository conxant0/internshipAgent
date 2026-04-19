from unittest.mock import patch, MagicMock
import json
import tempfile
from pathlib import Path

SAMPLE_LISTINGS = [
    {
        "title": "Python Intern",
        "company": "Tech Co",
        "location": "Cebu",
        "deadline": "2099-12-31",
        "compensation": "Paid",
        "description": "Python Django backend work",
        "requirements": ["Python", "Django"],
        "source": "prosple",
        "url": "https://example.com/1",
    }
]


def make_tool_call(name, args):
    tc = MagicMock()
    tc.id = f"call_{name}"
    tc.function.name = name
    tc.function.arguments = json.dumps(args)
    return tc


def make_response(content=None, tool_calls=None):
    msg = MagicMock()
    msg.content = content or ""
    msg.tool_calls = tool_calls or []
    return msg


def test_agent_calls_write_report_and_returns_path(tmp_path):
    output_file = str(tmp_path / "report.md")

    responses = [
        make_response(tool_calls=[make_tool_call("filter_expired", {"listings": SAMPLE_LISTINGS})]),
        make_response(tool_calls=[make_tool_call("write_report", {"listings": SAMPLE_LISTINGS})]),
    ]

    with patch("agent.agent.chat", side_effect=responses), \
         patch("agent.agent.tool_fns.write_report", return_value=output_file) as mock_write:
        from agent.agent import run
        result = run(SAMPLE_LISTINGS)

    mock_write.assert_called_once()
    assert result == output_file


def test_agent_stops_if_no_tool_calls():
    response = make_response(content="I'm done.", tool_calls=[])

    with patch("agent.agent.chat", return_value=response):
        from agent.agent import run
        result = run(SAMPLE_LISTINGS)

    assert result is None


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
    (tmp_path / "filter_expired.json").write_text(json.dumps([{"title": "A"}]))
    (tmp_path / "enrich_listings.json").write_text(json.dumps([{"title": "B"}]))
    with patch("agent.agent._CHECKPOINT_DIR", tmp_path):
        from agent.agent import _load_latest_checkpoint, STAGE_ORDER
        stage, listings = _load_latest_checkpoint()
    assert stage == "enrich_listings"
    assert listings == [{"title": "B"}]


def test_run_saves_checkpoint_after_each_stage(tmp_path):
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


def test_run_resumes_from_checkpoint_skips_completed_stage(tmp_path):
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

    filter_mock.assert_called_once()
    assert result == output_file
