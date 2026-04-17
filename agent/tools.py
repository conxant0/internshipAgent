import logging
from datetime import date
from typing import List

import scrapers.prosple as _prosple
from agent.llm_client import chat

logger = logging.getLogger(__name__)

DESCRIPTION_FETCHERS = {
    "prosple": _prosple.fetch_description,
}

_ENRICH_MODEL = "llama-3.1-8b-instant"

_ENRICH_PROMPT = """Extract the following fields from this job description. Return ONLY a JSON object.
If a field is not mentioned, return null for that key.

Fields:
- compensation: string (e.g. "PHP 8000/month") or null
- deadline: string in YYYY-MM-DD format or null
- location: string (e.g. "Cebu City, Philippines") or null
- requirements: list of SPECIFIC technical skills only — tools, software, programming languages, platforms (e.g. ["Python", "React", "SQL", "MS Office"]). EXCLUDE soft skills (communication, teamwork), personality traits, degree requirements, industry interests, or anything that is not a concrete technical skill or tool. Return null if none found.

Description:
{description}"""


def fetch_descriptions(listings: List[dict]) -> List[dict]:
    """Fetch full description from each listing's detail page. Skips on error."""
    for listing in listings:
        fetcher = DESCRIPTION_FETCHERS.get(listing.get("source", ""))
        if fetcher and not listing.get("description"):
            try:
                listing["description"] = fetcher(listing["url"])
            except Exception as e:
                logger.warning(f"fetch_description failed for {listing.get('url')}: {e}")
    return listings


def enrich_listings(listings: List[dict]) -> List[dict]:
    """Use a small LLM to extract structured fields from each listing's description."""
    import json as _json
    for listing in listings:
        description = listing.get("description") or ""
        if not description:
            continue
        try:
            response = chat(
                [{"role": "user", "content": _ENRICH_PROMPT.format(description=description)}],
                model=_ENRICH_MODEL,
            )
            content = response.content.strip()
            if content.startswith("```"):
                content = content.split("```", 2)[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.rsplit("```", 1)[0].strip()
            extracted = _json.loads(content)
            for field in ("compensation", "deadline", "location", "requirements"):
                if extracted.get(field) is not None:
                    listing[field] = extracted[field]
        except Exception as e:
            logger.warning(f"enrich_listings failed for {listing.get('url')}: {e}")
    return listings


def filter_expired(listings: List[dict]) -> List[dict]:
    """Drop any listing whose deadline has already passed. Keep null deadlines."""
    today = date.today().isoformat()
    return [l for l in listings if l.get("deadline") is None or l["deadline"] >= today]


def score_listing(listings: List[dict]) -> List[dict]:
    """Add a 'score' field (0-100) to each listing. Returns a new list."""
    result = []
    for listing in listings:
        scored = dict(listing)
        scored["score"] = _compute_score(listing)
        result.append(scored)
    return result


def _compute_score(listing: dict) -> int:
    score = 0

    # Location — 25 pts
    location = (listing.get("location") or "").lower()
    if "cebu" in location:
        score += 25
    elif any(w in location for w in ["remote", "wfh", "work from home"]):
        score += 20

    # Skills match — 8 pts per skill, max 40
    skills = ["python", "django", "react", "aws", "docker"]
    text = (listing.get("description") or "").lower()
    text += " " + " ".join(r.lower() for r in (listing.get("requirements") or []))
    matched = sum(1 for skill in skills if skill in text)
    score += matched * 8

    # Internship type — 15 pts
    title = (listing.get("title") or "").lower()
    if any(w in title for w in ["intern", "ojt", "trainee"]):
        score += 15

    # Compensation — 10 pts
    compensation = (listing.get("compensation") or "").lower()
    if compensation and "unpaid" not in compensation:
        score += 10

    # Known deadline — 10 pts (null deadline is penalised)
    if listing.get("deadline"):
        score += 10

    return min(score, 100)


def deduplicate(listings: List[dict]) -> List[dict]:
    """Merge duplicates across sources. Keeps the version with most non-null fields."""
    source_priority = {"prosple": 0, "kalibrr": 1, "jobstreet": 2}
    seen: dict = {}

    for listing in listings:
        company = (listing.get("company") or "").lower().strip()
        title_words = frozenset((listing.get("title") or "").lower().split())
        key = (company, title_words)

        if key not in seen:
            seen[key] = listing
        else:
            existing = seen[key]
            existing_score = sum(1 for v in existing.values() if v is not None)
            new_score = sum(1 for v in listing.values() if v is not None)

            if new_score > existing_score:
                seen[key] = listing
            elif new_score == existing_score:
                ep = source_priority.get(existing.get("source", ""), 99)
                np = source_priority.get(listing.get("source", ""), 99)
                if np < ep:
                    seen[key] = listing

    return list(seen.values())


def rank_listings(listings: List[dict]) -> List[dict]:
    """Sort listings by score descending."""
    return sorted(listings, key=lambda x: x.get("score", 0), reverse=True)


def write_report(listings: List[dict], output_path: str = "") -> str:
    """Write the ranked report to a markdown file. Returns the file path."""
    import os
    from pathlib import Path
    if not output_path:
        output_path = str(Path(__file__).parent.parent / "output" / "report.md")
    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
    lines = ["# Internship Listings — Ranked Report\n"]

    for i, listing in enumerate(listings, 1):
        title        = listing.get("title") or "Untitled"
        company      = listing.get("company") or "Unknown"
        score        = listing.get("score", 0)
        location     = listing.get("location") or "Not specified"
        deadline     = listing.get("deadline") or "Not specified"
        compensation = listing.get("compensation") or "Not specified"
        description  = listing.get("description") or ""
        requirements = listing.get("requirements") or []
        url          = listing.get("url") or "#"

        lines.append(f"## #{i} — {title} @ {company}")
        lines.append(f"Score: {score}/100 | Location: {location} | Deadline: {deadline} | Compensation: {compensation}")
        if requirements:
            lines.append(f"Skills mentioned: {', '.join(requirements)}")
        lines.append("")
        if description:
            short = description[:300] + ("..." if len(description) > 300 else "")
            lines.append(short)
        lines.append("")
        lines.append(f"[View listing →]({url})")
        lines.append("")
        lines.append("---")
        lines.append("")

    content = "\n".join(lines)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)

    return output_path
