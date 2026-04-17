import json
import logging
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

logger = logging.getLogger(__name__)

URL = "https://ph.prosple.com/internships-and-ojt-philippines"


def scrape() -> list:
    try:
        html = _fetch_html()
        apollo_data = _extract_apollo_data(html)
        return [_normalise(v, apollo_data) for k, v in apollo_data.items() if k.startswith("Opportunity:")]
    except Exception as e:
        logger.warning(f"Prosple scraper failed: {e}")
        return []


def _fetch_html(url: str = URL, wait_until: str = "domcontentloaded") -> str:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        )
        page = context.new_page()
        page.goto(url, wait_until=wait_until, timeout=60000)
        page.wait_for_timeout(5000)
        html = page.content()
        browser.close()
    return html


def _extract_apollo_data(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    tag = soup.find("script", id="__NEXT_DATA__")
    if not tag:
        logger.warning("Prosple: __NEXT_DATA__ not found")
        return {}
    next_data = json.loads(tag.string)
    return next_data.get("props", {}).get("apolloState", {}).get("data", {})


def _resolve_ref(ref_obj: dict, apollo_data: dict) -> dict:
    ref = ref_obj.get("__ref", "")
    return apollo_data.get(ref, {})


def _normalise(raw: dict, apollo_data: dict) -> dict:
    # Company name from parentEmployer ref
    employer = _resolve_ref(raw.get("parentEmployer") or {}, apollo_data)
    company = employer.get("advertiserName") or employer.get("title")

    # Location: prefer the human-readable label from geoAddresses
    geo_addresses = raw.get("geoAddresses") or []
    if geo_addresses:
        location = geo_addresses[0].get("label") or raw.get("locationDescription")
    else:
        location = raw.get("locationDescription")

    # Deadline: ISO date (drop time component)
    close_date = raw.get("applicationsCloseDate")
    deadline = close_date[:10] if close_date else None

    # Compensation: "Paid" if salary data present and not hidden
    salary = raw.get("salary")
    if salary and not raw.get("hideSalary"):
        min_s = raw.get("minSalary")
        max_s = raw.get("maxSalary")
        rate = salary.get("rate", "")
        currency_label = _resolve_ref(salary.get("currency") or {}, apollo_data).get("label", "PHP")
        if min_s and max_s and min_s == max_s:
            compensation = f"Paid — {currency_label} {min_s}/{rate}"
        elif min_s and max_s:
            compensation = f"Paid — {currency_label} {min_s}–{max_s}/{rate}"
        else:
            compensation = "Paid"
    else:
        compensation = None

    # Description from overview summary (may be empty on list page)
    description = (raw.get("overview") or {}).get("summary") or ""

    # Requirements from studyFields labels
    study_fields = raw.get("studyFields") or []
    requirements = [sf.get("label") for sf in study_fields if sf.get("label")]

    # URL
    detail_path = raw.get("detailPageURL") or ""
    url = ("https://ph.prosple.com" + detail_path) if detail_path else URL

    return {
        "title": raw.get("title"),
        "company": company,
        "location": location,
        "deadline": deadline,
        "compensation": compensation,
        "description": description,
        "requirements": requirements,
        "source": "prosple",
        "url": url,
    }


def fetch_description(url: str) -> str:
    """Fetch the full description from a Prosple listing detail page."""
    html = _fetch_html(url, wait_until="load")
    apollo_data = _extract_apollo_data(html)
    for key, value in apollo_data.items():
        if key.startswith("Opportunity:"):
            full_html = (value.get("overview") or {}).get("fullText") or ""
            if full_html:
                return BeautifulSoup(full_html, "html.parser").get_text(separator=" ", strip=True)
            return ""
    return ""
