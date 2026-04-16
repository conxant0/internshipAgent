from datetime import date
from typing import List


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
    text += " ".join(r.lower() for r in (listing.get("requirements") or []))
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
