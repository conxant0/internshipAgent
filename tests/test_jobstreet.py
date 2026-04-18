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
