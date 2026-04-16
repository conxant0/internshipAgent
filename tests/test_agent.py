from unittest.mock import patch, MagicMock
import json

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
