import pytest
from unittest.mock import patch, MagicMock
from scrapers.jobstreet import _normalise, scrape


def _make_raw(**kwargs):
    base = {
        "id": "12345678",
        "title": "IT Intern",
        "companyName": "Acme Corp",
        "locations": [{"label": "Cebu City, Central Visayas"}],
        "salaryLabel": "₱15,000 – ₱20,000 per month",
        "teaser": "You will build internal tools using Python.",
        "workTypes": ["Intern"],
        "workArrangements": [],
    }
    base.update(kwargs)
    return base


def test_normalise_maps_all_fields():
    raw = _make_raw()
    result = _normalise(raw)
    assert result["title"] == "IT Intern"
    assert result["company"] == "Acme Corp"
    assert result["location"] == "Cebu City, Central Visayas"
    assert result["deadline"] is None
    assert result["compensation"] == "₱15,000 – ₱20,000 per month"
    assert result["description"] == "You will build internal tools using Python."
    assert result["requirements"] == []
    assert result["source"] == "jobstreet"
    assert result["url"] == "https://ph.jobstreet.com/job/12345678"


def test_normalise_no_salary():
    raw = _make_raw(salaryLabel="")
    result = _normalise(raw)
    assert result["compensation"] is None


def test_normalise_no_locations():
    raw = _make_raw(locations=[])
    result = _normalise(raw)
    assert result["location"] is None


def test_normalise_no_teaser():
    raw = _make_raw(teaser="")
    result = _normalise(raw)
    assert result["description"] == ""

def test_scrape_paginates_until_total_count():
    page1 = {"totalCount": 40, "data": [_make_raw(id=str(i)) for i in range(32)]}
    page2 = {"totalCount": 40, "data": [_make_raw(id=str(i)) for i in range(32, 40)]}

    with patch("scrapers.jobstreet._fetch_page", side_effect=[page1, page2]) as mock_fetch:
        results = scrape()
        
        assert mock_fetch.call_count == 2
        assert len(results) == 40

def test_scrape_stops_on_empty_page():
    page1 = {"totalCount": 10, "data": [_make_raw(id=str(i)) for i in range(10)]}
    page2 = {"totalCount": 10, "data": []}

    with patch("scrapers.jobstreet._fetch_page", side_effect=[page1, page2]):
        results = scrape()

    assert len(results) == 10

def test_scrape_returns_empty_on_error():
    with patch("scrapers.jobstreet._fetch_page", side_effect=Exception("network error")):
        results = scrape()

    assert results == []