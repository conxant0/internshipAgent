import json
import os
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


def _mock_chat_response(content: str):
    msg = MagicMock()
    msg.content = content
    return msg


SAMPLE_PROFILE_JSON = json.dumps({
    "skills": ["Python", "SQL", "React"],
    "degree": "BS Computer Science",
    "year_level": "3rd year",
    "experience_summary": "Built web apps using Django and React."
})


def test_parse_resume_returns_profile_dict(tmp_path):
    resume = tmp_path / "resume.pdf"
    resume.write_bytes(b"%PDF fake content")

    with patch("resume_parser._extract_text", return_value="resume text here"), \
         patch("resume_parser.chat", return_value=_mock_chat_response(SAMPLE_PROFILE_JSON)):
        from resume_parser import parse_resume
        profile = parse_resume(data_dir=tmp_path)

    assert isinstance(profile["skills"], list)
    assert isinstance(profile["degree"], str)
    assert isinstance(profile["year_level"], str)
    assert isinstance(profile["experience_summary"], str)


def test_parse_resume_saves_profile_json(tmp_path):
    resume = tmp_path / "resume.pdf"
    resume.write_bytes(b"%PDF fake content")

    with patch("resume_parser._extract_text", return_value="resume text here"), \
         patch("resume_parser.chat", return_value=_mock_chat_response(SAMPLE_PROFILE_JSON)):
        from resume_parser import parse_resume
        parse_resume(data_dir=tmp_path)

    assert (tmp_path / "profile.json").exists()
    saved = json.loads((tmp_path / "profile.json").read_text())
    assert saved["skills"] == ["Python", "SQL", "React"]


def test_parse_resume_skips_when_profile_is_newer(tmp_path):
    resume = tmp_path / "resume.pdf"
    resume.write_bytes(b"%PDF fake content")

    existing_profile = {"skills": ["Java"], "degree": "BS IT", "year_level": "4th year", "experience_summary": "Old."}
    profile_path = tmp_path / "profile.json"
    profile_path.write_text(json.dumps(existing_profile))

    # Make profile.json newer than resume
    future_time = os.path.getmtime(resume) + 100
    os.utime(profile_path, (future_time, future_time))

    called = []
    with patch("resume_parser.chat", side_effect=lambda *a, **kw: called.append(1)):
        from resume_parser import parse_resume
        profile = parse_resume(data_dir=tmp_path)

    assert len(called) == 0
    assert profile["skills"] == ["Java"]


def test_parse_resume_reparses_when_resume_is_newer(tmp_path):
    resume = tmp_path / "resume.pdf"
    resume.write_bytes(b"%PDF fake content")

    old_profile = {"skills": ["Java"], "degree": "BS IT", "year_level": "4th year", "experience_summary": "Old."}
    profile_path = tmp_path / "profile.json"
    profile_path.write_text(json.dumps(old_profile))

    # Make resume newer than profile.json
    future_time = os.path.getmtime(profile_path) + 100
    os.utime(resume, (future_time, future_time))

    with patch("resume_parser._extract_text", return_value="new resume text"), \
         patch("resume_parser.chat", return_value=_mock_chat_response(SAMPLE_PROFILE_JSON)):
        from resume_parser import parse_resume
        profile = parse_resume(data_dir=tmp_path)

    assert profile["skills"] == ["Python", "SQL", "React"]


def test_parse_resume_raises_when_no_resume(tmp_path):
    from resume_parser import parse_resume
    with pytest.raises(FileNotFoundError, match="No resume found"):
        parse_resume(data_dir=tmp_path)


def test_parse_resume_accepts_docx(tmp_path):
    resume = tmp_path / "resume.docx"
    resume.write_bytes(b"fake docx content")

    with patch("resume_parser._extract_text", return_value="resume text"), \
         patch("resume_parser.chat", return_value=_mock_chat_response(SAMPLE_PROFILE_JSON)):
        from resume_parser import parse_resume
        profile = parse_resume(data_dir=tmp_path)

    assert profile["skills"] == ["Python", "SQL", "React"]
