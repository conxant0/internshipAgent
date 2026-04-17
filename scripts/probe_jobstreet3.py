"""Probe the SEEK REST API and REDUX_DATA for full job listing data."""
import json
import re
import requests
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

URL = "https://ph.jobstreet.com/Intern-jobs-in-information-communication-technology/in-Philippines"

# Step 1: Get SEEK_REDUX_DATA from SSR HTML
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
    page.goto(URL, wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(3000)
    html = page.content()
    browser.close()

# Extract SEEK_REDUX_DATA
match = re.search(r'window\.SEEK_REDUX_DATA\s*=\s*(\{.*?\});\s*\n', html, re.DOTALL)
if match:
    raw = match.group(1)
    try:
        redux = json.loads(raw)
        print("SEEK_REDUX_DATA top-level keys:", list(redux.keys()))
        # Look for jobs in results
        for key, val in redux.items():
            if isinstance(val, dict):
                for subkey, subval in val.items():
                    if isinstance(subval, list) and subval and isinstance(subval[0], dict):
                        if any(k in str(subkey).lower() for k in ["job", "result", "listing"]):
                            print(f"\nredux['{key}']['{subkey}'] — {len(subval)} items")
                            print("First item keys:", list(subval[0].keys()))
                            print(json.dumps(subval[0], indent=2)[:2000])
    except json.JSONDecodeError as e:
        print(f"JSON parse error: {e}")
        print(raw[:500])
else:
    print("SEEK_REDUX_DATA not found")

# Step 2: Try the REST API directly
print("\n\n=== Trying REST API ===")
api_url = "https://ph.jobstreet.com/api/jobsearch/v5/search"
params = {
    "siteKey": "PH",
    "where": "Philippines",
    "keywords": "Intern",
    "classification": "6281",  # ICT classification
    "pageSize": 10,
    "page": 1,
    "locale": "en-PH",
}
headers = {
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Referer": URL,
}
try:
    resp = requests.get(api_url, params=params, headers=headers, timeout=15)
    print(f"Status: {resp.status_code}")
    print(f"Content-Type: {resp.headers.get('content-type')}")
    if resp.status_code == 200:
        data = resp.json()
        print("Top-level keys:", list(data.keys()))
        for key in ("data", "jobs", "results", "hits"):
            if key in data:
                val = data[key]
                print(f"data['{key}'] type={type(val).__name__}", end="")
                if isinstance(val, list):
                    print(f" len={len(val)}")
                    if val and isinstance(val[0], dict):
                        print("First item keys:", list(val[0].keys()))
                        print(json.dumps(val[0], indent=2)[:2000])
                else:
                    print()
    else:
        print(resp.text[:500])
except Exception as e:
    print(f"Error: {e}")
