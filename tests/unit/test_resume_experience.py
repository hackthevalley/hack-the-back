from pathlib import Path

from app.services import resume_experience
from app.services.resume_experience import ResumeLine


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
