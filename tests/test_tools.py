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
