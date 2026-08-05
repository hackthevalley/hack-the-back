import importlib
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.models.forms import Forms_AnswerFile
from app.routers.admin.account import get_resume_experience
from app.services import resume_experience
from app.services.resume_experience import CompanyMatch, ResumeLine


account_router = importlib.import_module("app.routers.admin.account")


def _lines(*values: str) -> list[ResumeLine]:
    return [ResumeLine(text=value, page=1) for value in values]


def test_extracts_companies_near_dates_and_deduplicates(monkeypatch):
    monkeypatch.setattr(
        resume_experience,
        "_extract_lines",
        lambda _path: _lines(
            "EDUCATION",
            "Example University",
            "EXPERIENCE",
            "Acme Corporation | Toronto, ON",
            "Software Engineering Intern | May 2024 - Aug 2024",
            "• Built internal APIs",
            "ACME Corp.",
            "Developer | Sep 2024 - Present",
            "PROJECTS",
            "Personal Website | 2023 - 2024",
        ),
    )

    companies = resume_experience.extract_experience_companies(Path("resume.pdf"))

    assert [company.name for company in companies] == ["Acme Corporation"]
    assert companies[0].page == 1
    assert companies[0].confidence >= 0.8


def test_extracts_company_from_same_line(monkeypatch):
    monkeypatch.setattr(
        resume_experience,
        "_extract_lines",
        lambda _path: _lines(
            "Professional Experience",
            "Backend Engineer at Northstar Labs | 2022 - Present",
            "Education",
            "Example University",
        ),
    )

    companies = resume_experience.extract_experience_companies(Path("resume.pdf"))

    assert [company.name for company in companies] == ["Northstar Labs"]


def test_ignores_dates_outside_experience_section(monkeypatch):
    monkeypatch.setattr(
        resume_experience,
        "_extract_lines",
        lambda _path: _lines(
            "Education",
            "Example University | 2020 - 2024",
            "Projects",
            "Acme App | 2023 - Present",
        ),
    )

    assert resume_experience.extract_experience_companies(Path("resume.pdf")) == []


def test_extract_lines_preserves_nonempty_lines_and_limits_text(monkeypatch):
    pages = [
        SimpleNamespace(extract_text=lambda **_kwargs: " Experience \n\n Acme Corp "),
        SimpleNamespace(extract_text=lambda **_kwargs: "ignored"),
    ]
    monkeypatch.setattr(
        resume_experience, "PdfReader", lambda _path: SimpleNamespace(pages=pages)
    )
    monkeypatch.setattr(resume_experience, "MAX_TEXT_LENGTH", 25)

    assert resume_experience._extract_lines(Path("resume.pdf")) == [
        ResumeLine(text="Experience", page=1),
        ResumeLine(text="Acme Corp", page=1),
    ]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("", -100),
        ("• Built APIs", -100),
        ("Toronto, ON", -100),
        ("Education", -100),
        ("one two three four five six seven eight nine ten eleven", -100),
        ("Software Engineer: May 2020 - Present", -1),
    ],
)
def test_candidate_scoring_rejects_non_company_lines(text, expected):
    assert resume_experience._candidate_score(text, 0) == expected


def test_adjacent_date_entries_and_empty_company_are_ignored(monkeypatch):
    monkeypatch.setattr(
        resume_experience,
        "_extract_lines",
        lambda _path: _lines(
            "Experience",
            "Software Engineer | 2020 - 2021",
            "### | 2021 - 2022",
        ),
    )

    assert resume_experience.extract_experience_companies(Path("resume.pdf")) == []


def _session_with_resume(resume):
    session = MagicMock()
    session.exec.return_value.first.return_value = resume
    return session


def test_resume_experience_endpoint_returns_matches(tmp_path, monkeypatch):
    resume_path = tmp_path / "resume.pdf"
    resume_path.write_bytes(b"pdf")
    resume = Forms_AnswerFile(
        application_id=uuid4(), question_id=uuid4(), file_path=str(resume_path)
    )
    monkeypatch.setattr(
        account_router,
        "extract_experience_companies",
        lambda _path: [CompanyMatch("Acme Corp", 0.94, "Acme Corp", 1)],
    )

    response = get_resume_experience(
        resume.application_id, _session_with_resume(resume)
    )

    assert response == {
        "companies": [
            {
                "name": "Acme Corp",
                "confidence": 0.94,
                "source_text": "Acme Corp",
                "page": 1,
            }
        ]
    }


@pytest.mark.parametrize(
    "resume",
    [None, Forms_AnswerFile(application_id=uuid4(), question_id=uuid4())],
)
def test_resume_experience_endpoint_requires_resume(resume):
    with pytest.raises(HTTPException) as caught:
        get_resume_experience(uuid4(), _session_with_resume(resume))
    assert caught.value.status_code == 404


def test_resume_experience_endpoint_handles_missing_and_invalid_files(
    tmp_path, monkeypatch
):
    resume = Forms_AnswerFile(
        application_id=uuid4(),
        question_id=uuid4(),
        file_path=str(tmp_path / "missing.pdf"),
    )
    with pytest.raises(HTTPException) as missing:
        get_resume_experience(resume.application_id, _session_with_resume(resume))
    assert missing.value.detail == "File not found on disk"

    resume_path = tmp_path / "resume.pdf"
    resume_path.write_bytes(b"invalid")
    resume.file_path = str(resume_path)
    monkeypatch.setattr(
        account_router,
        "extract_experience_companies",
        MagicMock(side_effect=ValueError("invalid PDF")),
    )
    with pytest.raises(HTTPException) as invalid:
        get_resume_experience(resume.application_id, _session_with_resume(resume))
    assert invalid.value.status_code == 422
