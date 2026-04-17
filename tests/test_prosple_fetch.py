import json
from unittest.mock import patch
from scrapers.prosple import fetch_description


def _make_next_data(full_text):
    return f"""<html><head><script id="__NEXT_DATA__" type="application/json">
{json.dumps({
    "props": {
        "apolloState": {
            "data": {
                "Opportunity:abc": {
                    "overview": {"summary": "", "fullText": full_text}
                }
            }
        }
    }
})}
</script></head></html>"""


def test_fetch_description_returns_full_text():
    html = _make_next_data("<p>Full job <strong>description</strong> here.</p>")
    with patch("scrapers.prosple._fetch_html", return_value=html):
        result = fetch_description("https://ph.prosple.com/some-job")
    assert result == "Full job description here."


def test_fetch_description_returns_empty_when_no_opportunity_key():
    html = """<html><head><script id="__NEXT_DATA__" type="application/json">
{"props": {"apolloState": {"data": {"SomethingElse:123": {}}}}}
</script></head></html>"""
    with patch("scrapers.prosple._fetch_html", return_value=html):
        result = fetch_description("https://ph.prosple.com/some-job")
    assert result == ""


def test_fetch_description_returns_empty_when_no_next_data():
    with patch("scrapers.prosple._fetch_html", return_value="<html></html>"):
        result = fetch_description("https://ph.prosple.com/some-job")
    assert result == ""


def test_fetch_description_returns_empty_when_full_text_missing():
    html = _make_next_data(None)
    with patch("scrapers.prosple._fetch_html", return_value=html):
        result = fetch_description("https://ph.prosple.com/some-job")
    assert result == ""
