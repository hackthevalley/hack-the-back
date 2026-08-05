import re
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader


MAX_PAGES = 10
MAX_TEXT_LENGTH = 100_000

EXPERIENCE_HEADINGS = {
    "experience",
    "work experience",
    "professional experience",
    "employment",
    "employment history",
    "work history",
    "relevant experience",
}
END_HEADINGS = {
    "activities",
    "awards",
    "certifications",
    "education",
    "interests",
    "leadership",
    "projects",
    "publications",
    "skills",
    "technical skills",
    "volunteering",
}

MONTH = (
    r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
    r"jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|"
    r"dec(?:ember)?)"
)
DATE_VALUE = rf"(?:{MONTH}\.?\s+\d{{2,4}}|\d{{1,2}}[/-]\d{{2,4}}|\d{{4}})"
DATE_RANGE = re.compile(
    rf"\b{DATE_VALUE}\s*(?:-|–|—|to)\s*(?:{DATE_VALUE}|present|current|now)\b",
    re.IGNORECASE,
)
COMPANY_SUFFIX = re.compile(
    r"\b(?:co(?:mpany)?|corp(?:oration)?|inc(?:orporated)?|labs?|limited|ltd|"
    r"llc|lp|partners?|group|bank|technologies|technology|systems|solutions)\.?\b",
    re.IGNORECASE,
)
JOB_TITLE = re.compile(
    r"\b(?:analyst|architect|assistant|associate|consultant|coordinator|designer|"
    r"developer|director|engineer|founder|intern|lead|manager|officer|president|"
    r"researcher|scientist|specialist|supervisor|technician|volunteer)\b",
    re.IGNORECASE,
)
BULLET_PREFIX = re.compile(r"^\s*(?:[•●▪◦*-]|\d+[.)])\s+")
LOCATION_ONLY = re.compile(
    r"^(?:remote|hybrid|on[ -]site|[A-Za-z .'-]+,\s*[A-Z]{2}|"
    r"[A-Za-z .'-]+,\s*(?:Canada|USA|United States))$",
    re.IGNORECASE,
)
TRAILING_LOCATION = re.compile(
    r"\s*(?:\||·|—)\s*(?:remote|hybrid|on[ -]site|[A-Za-z .'-]+,\s*[A-Z]{2}|"
    r"[A-Za-z .'-]+,\s*(?:Canada|USA|United States))\s*$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ResumeLine:
    text: str
    page: int


@dataclass(frozen=True)
class CompanyMatch:
    name: str
    confidence: float
    source_text: str
    page: int


def _normalize_heading(text: str) -> str:
    return re.sub(r"[^a-z ]", "", text.casefold()).strip()


def _is_heading(line: ResumeLine, choices: set[str]) -> bool:
    normalized = _normalize_heading(line.text)
    return len(line.text) <= 40 and normalized in choices


def _extract_lines(path: Path) -> list[ResumeLine]:
    reader = PdfReader(path)
    lines: list[ResumeLine] = []
    extracted_characters = 0

    for page_number, page in enumerate(reader.pages[:MAX_PAGES], start=1):
        # Layout mode preserves columns and line boundaries better than plain extraction.
        text = page.extract_text(extraction_mode="layout") or ""
        remaining = MAX_TEXT_LENGTH - extracted_characters
        if remaining <= 0:
            break
        text = text[:remaining]
        extracted_characters += len(text)
        lines.extend(
            ResumeLine(text=raw_line.strip(), page=page_number)
            for raw_line in text.splitlines()
            if raw_line.strip()
        )

    return lines


def _experience_lines(lines: list[ResumeLine]) -> list[ResumeLine]:
    start = next(
        (
            index + 1
            for index, line in enumerate(lines)
            if _is_heading(line, EXPERIENCE_HEADINGS)
        ),
        None,
    )
    if start is None:
        return []

    end = next(
        (
            index
            for index in range(start, len(lines))
            if _is_heading(lines[index], END_HEADINGS)
        ),
        len(lines),
    )
    return lines[start:end]


def _candidate_fragments(text: str) -> list[str]:
    without_dates = DATE_RANGE.sub("", text)
    without_dates = TRAILING_LOCATION.sub("", without_dates).strip(" ,;|·—–-")
    fragments = [without_dates]
    fragments.extend(re.split(r"\s+(?:\||·|—|–)\s+", without_dates))

    at_match = re.search(r"\bat\s+(.+)$", without_dates, re.IGNORECASE)
    if at_match:
        fragments.append(at_match.group(1))

    return list(dict.fromkeys(fragment.strip(" ,;|·—–-") for fragment in fragments))


def _candidate_score(text: str, distance: int) -> int:
    if (
        not text
        or BULLET_PREFIX.match(text)
        or LOCATION_ONLY.match(text)
        or _normalize_heading(text) in EXPERIENCE_HEADINGS | END_HEADINGS
    ):
        return -100

    word_count = len(text.split())
    if word_count > 10 or len(text) > 100:
        return -100

    score = 4 - min(distance, 3)
    if 1 <= word_count <= 6:
        score += 2
    if COMPANY_SUFFIX.search(text):
        score += 3
    if JOB_TITLE.search(text):
        score -= 5
    if DATE_RANGE.search(text):
        score -= 2
    if text.endswith(('.', ':')):
        score -= 1
    return score


def _company_key(name: str) -> str:
    normalized = re.sub(r"[^a-z0-9 ]", " ", name.casefold())
    normalized = re.sub(
        r"\b(?:company|co|corporation|corp|incorporated|inc|limited|ltd|llc)\b",
        "",
        normalized,
    )
    return re.sub(r"\s+", " ", normalized).strip()


def extract_experience_companies(path: Path) -> list[CompanyMatch]:
    section = _experience_lines(_extract_lines(path))
    matches: dict[str, CompanyMatch] = {}

    for date_index, date_line in enumerate(section):
        if not DATE_RANGE.search(date_line.text):
            continue

        candidates: list[tuple[int, str, ResumeLine]] = []
        for index in range(max(0, date_index - 2), min(len(section), date_index + 2)):
            line = section[index]
            if index != date_index and DATE_RANGE.search(line.text):
                continue
            distance = abs(index - date_index)
            for fragment in _candidate_fragments(line.text):
                candidates.append((_candidate_score(fragment, distance), fragment, line))

        if not candidates:
            continue
        score, name, source = max(candidates, key=lambda candidate: candidate[0])
        if score < 4:
            continue

        key = _company_key(name)
        if not key:
            continue
        match = CompanyMatch(
            name=name,
            confidence=round(min(0.99, 0.45 + score * 0.07), 2),
            source_text=source.text,
            page=source.page,
        )
        if key not in matches or match.confidence > matches[key].confidence:
            matches[key] = match

    return list(matches.values())
