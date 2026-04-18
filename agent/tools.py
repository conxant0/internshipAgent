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
- compensation: string including amount and frequency if mentioned (e.g. "PHP 8000/month", "PHP 500/day", "PHP 2000/week", "PHP 10000 upon completion"). Include the frequency (monthly, weekly, daily, upon completion) when stated. or null
- deadline: string in YYYY-MM-DD format or null
- location: string (e.g. "Cebu City, Philippines") or null
- summary: 1-2 sentence plain description of what the intern will actually do in the role. Focus on responsibilities only. Do not mention skills, tools, compensation, or requirements — those are captured separately. No filler phrases like "join our team" or "exciting opportunity". Return null if unclear.
- requirements: list of SPECIFIC technical skills only — tools, software, programming languages, platforms (e.g. ["Python", "React", "SQL", "MS Office"]). EXCLUDE soft skills (communication, teamwork), personality traits, degree/course requirements (e.g. "BS Computer Science"), year level, graduation timelines, citizenship, visa, or anything that is not a concrete technical tool or skill — those belong in eligibility. Return null if none found.
- eligibility: list of plain-English eligibility constraints — year level (e.g. "3rd year students only"), hours to render (e.g. "480 hours required"), internship type (e.g. "voluntary internship only", "academic internship only", "for-credit internship"), course/degree restrictions (e.g. "BS Computer Science only"), citizenship or visa requirements, graduation timelines. Each item is a short phrase. Do NOT include technical tools or skills here — those belong in requirements. Return null if none found.

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
            for field in ("compensation", "deadline", "location", "requirements", "summary", "eligibility"):
                if extracted.get(field):
                    listing[field] = extracted[field]
        except Exception as e:
            logger.warning(f"enrich_listings failed for {listing.get('url')}: {e}")
    return listings


def filter_expired(listings: List[dict]) -> List[dict]:
    """Drop any listing whose deadline has already passed. Keep null deadlines."""
    today = date.today().isoformat()
    return [l for l in listings if l.get("deadline") is None or l["deadline"] >= today]


_CS_IT_KEYWORDS = [
    "computer",
    "information technology",
    " it ",  # "IT" abbreviation — padded to avoid substring false positives
    "software",
    "engineering",
    "stem",
    "technology",
    "data science",
    "all course",
    "any course",
    "open to all",
]

_NON_CS_IT_KEYWORDS = [
    "nurs",
    "law ",
    " law",
    "medic",
    "dental",
    "pharmac",
    "fine art",
    "criminolog",
    "journali",
    "psycholog",
    "social work",
    "accountanc",
    "hotel",
    "tourism",
    "culinar",
    "agricultur",
    "veterinar",
    "education major",
    "teacher education",
    "liberal arts",
]


def _eligibility_excludes_cs_it(eligibility: list[str]) -> bool:
    """Return True when eligibility clearly restricts to a non-CS/IT field.

    Returns False (keep) when no non-CS keyword is found, or when a CS/IT
    keyword co-occurs (benefit of the doubt for mixed-field listings).
    """
    joined = " " + " ".join(eligibility).lower() + " "
    if any(kw in joined for kw in _CS_IT_KEYWORDS):
        return False
    return any(kw in joined for kw in _NON_CS_IT_KEYWORDS)


def filter_ineligible(listings: list[dict]) -> list[dict]:
    """Drop listings with post-enrichment expired deadlines or eligibility
    constraints that restrict to a non-CS/IT course field."""
    today = date.today().isoformat()
    result = []
    for listing in listings:
        deadline = listing.get("deadline")
        if deadline is not None and deadline < today:
            logger.info(
                f"filter_ineligible: dropping expired '{listing.get('title')}' (deadline {deadline})"
            )
            continue

        eligibility = listing.get("eligibility") or []
        if eligibility and _eligibility_excludes_cs_it(eligibility):
            logger.info(
                f"filter_ineligible: dropping non-CS/IT '{listing.get('title')}' (eligibility: {eligibility})"
            )
            continue

        result.append(listing)
    return result


_SCORE_MODEL = "llama-3.3-70b-versatile"

_SCORE_PROMPT = """Score this internship listing for the candidate below. Return ONLY a JSON object.

Scoring framework (total = 100 pts):
- Skills match (25 pts): How well the candidate's existing skills align with the listing's requirements.
- Role relevance (20 pts): How closely the listing title and responsibilities match the candidate's target role: {target_role}.
- Eligibility fit (20 pts): Whether the candidate meets year level, degree, citizenship, or hours requirements.
- Location (20 pts): Candidate prefers {location_preference}. Cebu-based or remote = 20 pts; onsite in other PH cities = 10 pts; international onsite = 2 pts.
- Compensation (15 pts): Paid = 15 pts; unpaid = 0 pts; unspecified = 7 pts.

Candidate profile:
{profile_json}

Listing:
Title: {title}
Company: {company}
Location: {location}
Description: {description}
Requirements: {requirements}
Eligibility: {eligibility}

Return ONLY: {{"score": <int 0-100>, "rationale": "<2-3 sentence explanation of the score>"}}"""


def score_listing(listings: List[dict], profile: dict, preferences: dict) -> List[dict]:
    """Score each listing 0-100 using LLM with the user's profile and preferences."""
    import json as _json
    result = []
    for listing in listings:
        scored = dict(listing)
        prompt = _SCORE_PROMPT.format(
            target_role=preferences.get("target_role", ""),
            location_preference=preferences.get("location_preference", ""),
            profile_json=_json.dumps(profile, indent=2),
            title=listing.get("title") or "",
            company=listing.get("company") or "",
            location=listing.get("location") or "Not specified",
            description=listing.get("description") or "",
            requirements=", ".join(r for r in (listing.get("requirements") or []) if r) or "Not specified",
            eligibility=", ".join(listing.get("eligibility") or []) or "Not specified",
        )
        raw = None
        for attempt in range(2):
            try:
                response = chat(
                    [{"role": "user", "content": prompt}],
                    model=_SCORE_MODEL,
                )
                raw = response.content
                content = response.content.strip()
                if content.startswith("```"):
                    content = content.split("```", 2)[1]
                    if content.startswith("json"):
                        content = content[4:]
                    content = content.rsplit("```", 1)[0].strip()
                parsed = _json.loads(content)
                scored["score"] = int(parsed["score"])
                scored["rationale"] = parsed["rationale"]
                break
            except Exception:
                pass
        else:
            logger.warning(f"score_listing failed after 2 attempts for '{listing.get('title')}'; assigning score=0. Last LLM output: {raw!r}")
            scored["score"] = 0
            scored["rationale"] = ""
        result.append(scored)
    return result


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
        requirements = listing.get("requirements") or []
        summary      = listing.get("summary") or ""
        rationale    = listing.get("rationale") or ""
        url          = listing.get("url") or "#"

        lines.append(f"## #{i} — {title} @ {company}")
        lines.append(f"Score: {score}/100")
        if rationale:
            lines.append(f"Why: {rationale}")
        lines.append(f"Location: {location}")
        lines.append(f"Deadline: {deadline}")
        lines.append(f"Compensation: {compensation}")
        if requirements:
            lines.append(f"Skills: {', '.join(str(r) for r in requirements)}")
        eligibility = listing.get("eligibility") or []
        if eligibility:
            lines.append(f"Eligibility: {', '.join(eligibility)}")
        lines.append("")
        if summary:
            lines.append(summary)
        lines.append("")
        lines.append(f"[View listing →]({url})")
        lines.append("")
        lines.append("---")
        lines.append("")

    content = "\n".join(lines)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)

    return output_path
