"""Check if job listings are embedded in the SSR HTML."""
import json
import re
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

URL = "https://ph.jobstreet.com/Intern-jobs-in-information-communication-technology/in-Philippines"

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

soup = BeautifulSoup(html, "html.parser")

# Check all script tags for JSON job data
print("=== Script tags with JSON content ===")
for tag in soup.find_all("script"):
    src = tag.get("src")
    if src:
        continue
    text = (tag.string or "").strip()
    if not text:
        continue
    # Look for job-like content
    if any(kw in text.lower() for kw in ["jobid", "jobtitle", "advertiser", "listingdate", "salary", '"id"']):
        print(f"\nTag type={tag.get('type')} id={tag.get('id')}")
        print(text[:3000])
    elif text.startswith("{") or text.startswith("["):
        print(f"\nJSON tag (id={tag.get('id')}, type={tag.get('type')}):")
        print(text[:500])

# Check for window.__* variables
print("\n=== window.__ variables ===")
for match in re.finditer(r'window\.__(\w+)\s*=\s*(\{.*?\});', html, re.DOTALL):
    name = match.group(1)
    val = match.group(2)
    print(f"window.__{name}: {val[:300]}")

# Look for job listings in article/li elements
print("\n=== Job article elements ===")
articles = soup.find_all("article")
print(f"Found {len(articles)} article elements")
if articles:
    print("First article attrs:", articles[0].attrs)
    print("First article text (first 200 chars):", articles[0].get_text()[:200])

# Check data-* attrs that look like job data
print("\n=== Elements with data-job-id or similar ===")
for elem in soup.find_all(attrs={"data-job-id": True}):
    print(elem.attrs)
    break
for elem in soup.find_all(attrs={"data-automation": True}):
    val = elem.get("data-automation", "")
    if "job" in val.lower():
        print(f"data-automation={val}: {str(elem)[:200]}")
        break
