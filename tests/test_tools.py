import pytest
from agent.tools import filter_expired, score_listing

# ── Fixtures ─────────────────────────────────────────────────────────────────

FUTURE = "2099-12-31"
PAST   = "2000-01-01"

def make_listing(**kwargs):
    base = {
        "title": "Software Engineering Intern",
        "company": "Tech Corp",
        "location": "Cebu",
        "deadline": FUTURE,
        "compensation": "Paid",
        "description": "We use Python and Django for our backend.",
        "requirements": ["Python", "Django"],
        "source": "prosple",
        "url": "https://example.com/1",
    }
    base.update(kwargs)
    return base

# ── filter_expired ────────────────────────────────────────────────────────────

def test_filter_expired_removes_past_deadlines():
    listings = [
        make_listing(deadline=FUTURE),
        make_listing(deadline=PAST),
    ]
    result = filter_expired(listings)
    assert len(result) == 1
    assert result[0]["deadline"] == FUTURE

def test_filter_expired_keeps_null_deadline():
    listings = [make_listing(deadline=None)]
    result = filter_expired(listings)
    assert len(result) == 1

def test_filter_expired_empty_list():
    assert filter_expired([]) == []

# ── score_listing ─────────────────────────────────────────────────────────────

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
    with patch("agent.tools.chat", return_value=_mock_score_response(70, "Skills align well.")):
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

# ── deduplicate ───────────────────────────────────────────────────────────────

from agent.tools import deduplicate, rank_listings, write_report
import os

def test_deduplicate_removes_exact_duplicate():
    a = make_listing(source="prosple")
    b = make_listing(source="kalibrr")  # same company+title, different source
    result = deduplicate([a, b])
    assert len(result) == 1

def test_deduplicate_keeps_richer_version():
    sparse = make_listing(description=None, compensation=None, source="kalibrr")
    rich   = make_listing(description="Full description here", compensation="Paid", source="prosple")
    result = deduplicate([sparse, rich])
    assert result[0]["description"] == "Full description here"

def test_deduplicate_keeps_different_companies():
    a = make_listing(company="Company A")
    b = make_listing(company="Company B")
    result = deduplicate([a, b])
    assert len(result) == 2

# ── rank_listings ─────────────────────────────────────────────────────────────

def test_rank_listings_sorted_descending():
    listings = [
        make_listing(score=40),
        make_listing(score=90),
        make_listing(score=60),
    ]
    result = rank_listings(listings)
    assert result[0]["score"] == 90
    assert result[1]["score"] == 60
    assert result[2]["score"] == 40

# ── write_report ──────────────────────────────────────────────────────────────

def test_write_report_creates_file(tmp_path):
    listings = [make_listing(score=85)]
    output_file = str(tmp_path / "report.md")
    path = write_report(listings, output_path=output_file)
    assert os.path.exists(path)

def test_write_report_contains_title(tmp_path):
    listings = [make_listing(title="Python Intern", score=85)]
    output_file = str(tmp_path / "report.md")
    write_report(listings, output_path=output_file)
    content = open(output_file).read()
    assert "Python Intern" in content

def test_write_report_contains_rank_number(tmp_path):
    listings = [make_listing(score=85)]
    output_file = str(tmp_path / "report.md")
    write_report(listings, output_path=output_file)
    content = open(output_file).read()
    assert "#1" in content

def test_write_report_shows_eligibility(tmp_path):
    listing = make_listing(score=80, eligibility=["3rd year CS students only", "480 hours required"])
    output_file = str(tmp_path / "report.md")
    write_report([listing], output_path=output_file)
    content = open(output_file).read()
    assert "Eligibility:" in content
    assert "3rd year CS students only" in content
    assert "480 hours required" in content

def test_write_report_omits_eligibility_when_absent(tmp_path):
    listing = make_listing(score=80)
    output_file = str(tmp_path / "report.md")
    write_report([listing], output_path=output_file)
    content = open(output_file).read()
    assert "Eligibility:" not in content

# ── fetch_descriptions ────────────────────────────────────────────────────────

from unittest.mock import patch, MagicMock
from agent.llm_client import chat
from agent.tools import fetch_descriptions


def test_chat_uses_custom_model():
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_client.chat.completions.create.return_value = mock_response

    with patch("agent.llm_client.Groq", return_value=mock_client):
        chat([{"role": "user", "content": "hi"}], model="llama-3.1-8b-instant")

    call_kwargs = mock_client.chat.completions.create.call_args[1]
    assert call_kwargs["model"] == "llama-3.1-8b-instant"

def test_fetch_descriptions_populates_description():
    listings = [make_listing(description="", source="prosple")]

    def mock_fetcher(url):
        return "Full description text."

    with patch.dict("agent.tools.DESCRIPTION_FETCHERS", {"prosple": mock_fetcher}, clear=True):
        result = fetch_descriptions(listings)

    assert result[0]["description"] == "Full description text."

def test_fetch_descriptions_skips_unknown_source():
    listings = [make_listing(description="", source="kalibrr")]
    result = fetch_descriptions(listings)
    assert result[0]["description"] == ""

def test_fetch_descriptions_skips_already_populated():
    listings = [make_listing(description="existing text", source="prosple")]

    called = []

    def mock_fetcher(url):
        called.append(url)
        return "new description"

    with patch.dict("agent.tools.DESCRIPTION_FETCHERS", {"prosple": mock_fetcher}, clear=True):
        result = fetch_descriptions(listings)

    assert result[0]["description"] == "existing text"
    assert len(called) == 0

def test_fetch_descriptions_continues_on_error():
    listings = [
        make_listing(description="", source="prosple", url="https://example.com/1"),
        make_listing(description="", source="prosple", url="https://example.com/2"),
    ]

    def mock_fetcher(url):
        if "1" in url:
            raise Exception("Timeout")
        return "Good description"

    with patch.dict("agent.tools.DESCRIPTION_FETCHERS", {"prosple": mock_fetcher}, clear=True):
        result = fetch_descriptions(listings)

    assert result[0]["description"] == ""
    assert result[1]["description"] == "Good description"


# ── enrich_listings ───────────────────────────────────────────────────────────

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
    assert result[0]["compensation"] == "Paid"

def test_enrich_strips_markdown_code_fences():
    listing = make_listing(description=ENRICH_DESCRIPTION, compensation="Paid")
    with patch("agent.tools.chat", return_value=_mock_llm_response(
        '```json\n{"compensation": "PHP 9000/month", "deadline": null, "location": null, "requirements": null}\n```'
    )):
        result = enrich_listings([listing])
    assert result[0]["compensation"] == "PHP 9000/month"

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
