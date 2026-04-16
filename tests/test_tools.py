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

def test_score_listing_returns_int():
    listing = make_listing()
    scores = score_listing([listing])
    assert isinstance(scores[0]["score"], int)

def test_score_listing_cebu_scores_higher_than_manila():
    cebu   = make_listing(location="Cebu")
    manila = make_listing(location="Manila")
    cebu_score   = score_listing([cebu])[0]["score"]
    manila_score = score_listing([manila])[0]["score"]
    assert cebu_score > manila_score

def test_score_listing_skills_match_adds_points():
    with_skills    = make_listing(description="We use Python, Django, React, AWS, Docker")
    without_skills = make_listing(description="No relevant tech mentioned")
    high = score_listing([with_skills])[0]["score"]
    low  = score_listing([without_skills])[0]["score"]
    assert high > low

def test_score_listing_score_is_between_0_and_100():
    listing = make_listing()
    score = score_listing([listing])[0]["score"]
    assert 0 <= score <= 100

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
