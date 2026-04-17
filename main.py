import argparse
import json
import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

BASE = Path(__file__).parent


def run_scrapers():
    from scrapers.prosple import scrape as scrape_prosple

    (BASE / "data" / "raw").mkdir(parents=True, exist_ok=True)

    for name, fn in [("prosple", scrape_prosple)]:
        logger.info(f"Scraping {name}...")
        listings = fn()
        path = BASE / "data" / "raw" / f"{name}.json"
        with open(path, "w") as f:
            json.dump(listings, f, indent=2)
        logger.info(f"  -> saved {len(listings)} listings to {path}")


def load_raw_data() -> list:
    raw_dir = BASE / "data" / "raw"
    listings = []
    for json_file in raw_dir.glob("*.json"):
        with open(json_file) as f:
            data = json.load(f)
        listings.extend(data)
        logger.info(f"Loaded {len(data)} listings from {json_file.name}")
    return listings


def main():
    parser = argparse.ArgumentParser(description="Internship Agent")
    parser.add_argument("--skip-scrape", action="store_true", help="Skip scraping and use existing data in data/raw/")
    args = parser.parse_args()

    preferences_path = BASE / "data" / "preferences.json"
    if not preferences_path.exists():
        raise FileNotFoundError(
            "No preferences.json found at data/preferences.json. "
            "Please create it with your target_role and location_preference."
        )
    with open(preferences_path) as f:
        preferences = json.load(f)

    from resume_parser import parse_resume
    profile = parse_resume(data_dir=BASE / "data")

    if not args.skip_scrape:
        run_scrapers()

    listings = load_raw_data()
    if not listings:
        logger.error("No listings found. Run without --skip-scrape or check scrapers.")
        sys.exit(1)

    logger.info(f"Running agent on {len(listings)} listings...")

    from agent.agent import run
    report_path = run(listings, profile=profile, preferences=preferences)

    if report_path:
        logger.info(f"Done! Report saved to: {report_path}")
    else:
        logger.error("Agent did not produce a report.")
        sys.exit(1)


if __name__ == "__main__":
    main()
