import cloudscraper
import json
from bs4 import BeautifulSoup

url = "https://ph.prosple.com/internships-and-ojt-philippines"

scraper = cloudscraper.create_scraper()
response = scraper.get(url)
print(f"Status: {response.status_code}")

soup = BeautifulSoup(response.text, "html.parser")
next_data_tag = soup.find("script", id="__NEXT_DATA__")

if not next_data_tag:
    print("__NEXT_DATA__ not found")
    print("First 500 chars of response:")
    print(response.text[:500])
else:
    data = json.loads(next_data_tag.string)
    print(json.dumps(data, indent=2))
