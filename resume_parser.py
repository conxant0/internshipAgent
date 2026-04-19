import json
import os
from pathlib import Path

from agent.llm_client import chat

_PARSE_MODEL = "llama-3.3-70b-versatile"

_PARSE_PROMPT = """Extract the following fields from this resume. Return ONLY a JSON object with no extra text.

Fields:
- skills: list of technical skills, tools, and programming languages (e.g. ["Python", "SQL", "React"])
- degree: degree program (e.g. "BS Computer Science") or null
- year_level: current year level as a string (e.g. "3rd year") or null. If not explicitly stated, infer from expected graduation date using today's date ({today}) and a standard 4-year program (e.g. graduating in 4 years from enrollment = 4th year).
- experience_summary: 2-3 sentence summary of relevant experience and projects, or null

Resume:
{resume_text}"""

BASE = Path(__file__).parent


def _extract_text(resume_path: Path) -> str:
    suffix = resume_path.suffix.lower()
    if suffix == ".pdf":
        import pdfplumber
        with pdfplumber.open(resume_path) as pdf:
            return "\n".join(page.extract_text() or "" for page in pdf.pages)
    elif suffix in (".docx", ".doc"):
        from docx import Document
        doc = Document(resume_path)
        return "\n".join(p.text for p in doc.paragraphs)
    else:
        raise ValueError(f"Unsupported file type: {resume_path.suffix}")


def _find_resume(data_dir: Path) -> Path:
    for ext in (".pdf", ".docx"):
        candidate = data_dir / f"resume{ext}"
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        "No resume found at data/resume.pdf (or .docx). Please add your resume to get started."
    )


def parse_resume(data_dir: Path = None) -> dict:
    """Parse resume and return profile dict. Saves result to data/profile.json.
    Skips parsing if profile.json is newer than the resume file."""
    if data_dir is None:
        data_dir = BASE / "data"

    profile_path = data_dir / "profile.json"
    resume_path = _find_resume(data_dir)

    if profile_path.exists() and os.path.getmtime(profile_path) > os.path.getmtime(resume_path):
        with open(profile_path) as f:
            return json.load(f)

    resume_text = _extract_text(resume_path)
    from datetime import date
    response = chat(
        [{"role": "user", "content": _PARSE_PROMPT.format(resume_text=resume_text, today=date.today().isoformat())}],
        model=_PARSE_MODEL,
    )
    content = response.content.strip()
    if content.startswith("```"):
        content = content.split("```", 2)[1]
        if content.startswith("json"):
            content = content[4:]
        content = content.rsplit("```", 1)[0].strip()

    profile = json.loads(content)

    with open(profile_path, "w") as f:
        json.dump(profile, f, indent=2)

    return profile
