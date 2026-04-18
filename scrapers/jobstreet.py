import logging
import requests

logger = logging.getLogger(__name__)

_BASE_URL = "https://ph.jobstreet.com/api/jobsearch/v5/search"
_PAGE_SIZE = 32
_PARAMS = {
    "siteKey": "PH",
    "keywords": "Intern",
    "classification": "6281",
    "where": "Philippines",
    "locale": "en-PH",
    "pageSize": _PAGE_SIZE,
}
_HEADERS = {
    "Accept": "application/json",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": "https://ph.jobstreet.com/Intern-jobs-in-information-communication-technology/in-Philippines",
}


def scrape() -> list:
    try:
        results = []
        page = 1
        total = None
        while True:
            data = _fetch_page(page)
            if total is None:
                total = data.get("totalCount", 0)
            items = data.get("data", [])
            if not items:
                break
            results.extend(_normalise(item) for item in items)
            if len(results) >= total:
                break
            page += 1
        return results
    except Exception as e:
        logger.warning(f"JobStreet scraper failed: {e}")
        return []


def _fetch_page(page: int) -> dict:
    params = {**_PARAMS, "page": page}
    resp = requests.get(_BASE_URL, params=params, headers=_HEADERS, timeout=20)
    resp.raise_for_status()
    return resp.json()


def _normalise(raw: dict) -> dict:
    locations = raw.get("locations") or []
    location = locations[0]["label"] if locations else None

    salary = raw.get("salaryLabel") or ""
    compensation = salary if salary else None

    return {
        "title": raw.get("title"),
        "company": raw.get("companyName"),
        "location": location,
        "deadline": None,
        "compensation": compensation,
        "description": raw.get("teaser") or "",
        "requirements": [],
        "source": "jobstreet",
        "url": f"https://ph.jobstreet.com/job/{raw['id']}",
    }
