import json
import re
from collections.abc import Collection
from urllib.parse import urlsplit

from app.data.form_answer_config import (
    CHOICE_OPTIONS,
    INTEGER_RANGES,
    PROFILE_HOSTS,
    RACE_ETHNICITY_OPTIONS,
)

PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 128
PASSWORD_REQUIRE_UPPERCASE = True
PASSWORD_REQUIRE_LOWERCASE = True
PASSWORD_REQUIRE_DIGIT = True
PASSWORD_REQUIRE_SPECIAL = False


def validate_password_requirements(password: str) -> str:
    if len(password) < PASSWORD_MIN_LENGTH:
        raise ValueError(
            f"Password must be at least {PASSWORD_MIN_LENGTH} characters long"
        )

    if PASSWORD_REQUIRE_UPPERCASE and not any(c.isupper() for c in password):
        raise ValueError("Password must contain at least one uppercase letter")

    if PASSWORD_REQUIRE_LOWERCASE and not any(c.islower() for c in password):
        raise ValueError("Password must contain at least one lowercase letter")

    if PASSWORD_REQUIRE_DIGIT and not any(c.isdigit() for c in password):
        raise ValueError("Password must contain at least one number")

    if PASSWORD_REQUIRE_SPECIAL:
        special_chars = "!@#$%^&*()_+-=[]{}|;:,.<>?"
        if not any(c in special_chars for c in password):
            raise ValueError(
                f"Password must contain at least one special character ({special_chars})"
            )

    return password


def _validate_choice(label: str, value: str, options: Collection[str]) -> None:
    if value not in options:
        raise ValueError(f"Invalid option for {label}")


def _validate_multi_choice(label: str, value: str) -> None:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        parsed = [value]
    if not isinstance(parsed, list) or not parsed or not all(
        isinstance(option, str) for option in parsed
    ):
        raise ValueError(f"Invalid option for {label}")
    if len(parsed) != len(set(parsed)) or any(
        option not in RACE_ETHNICITY_OPTIONS for option in parsed
    ):
        raise ValueError(f"Invalid option for {label}")


def _validate_web_url(label: str, value: str) -> None:
    try:
        parsed = urlsplit(value)
    except ValueError as error:
        raise ValueError(f"Enter a valid URL for {label}") from error
    if (
        parsed.scheme.lower() not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise ValueError(f"Enter a valid URL for {label}")


def validate_form_answer(question_label: str, value: str | None) -> str | None:
    """Enforce form field constraints independently of the frontend."""
    if value is None or not value.strip():
        return value
    value = value.strip()

    options = CHOICE_OPTIONS.get(question_label)
    if options is not None:
        _validate_choice(question_label, value, options)
    elif question_label == "Race/Ethnicity (Select all that apply)":
        _validate_multi_choice(question_label, value)
    elif question_label in INTEGER_RANGES:
        minimum, maximum = INTEGER_RANGES[question_label]
        if not re.fullmatch(r"\d+", value) or not minimum <= int(value) <= maximum:
            raise ValueError(f"Invalid value for {question_label}")
    elif question_label == "Phone Number":
        if not re.fullmatch(r"[+()\-.\s\d]+", value):
            raise ValueError("Enter a valid phone number")
        digit_count = sum(character.isdigit() for character in value)
        if not 7 <= digit_count <= 15:
            raise ValueError("Enter a valid phone number")
    elif question_label == "Portfolio":
        _validate_web_url(question_label, value)

    validate_profile_url(question_label, value)
    return value


def validate_profile_url(
    question_label: str, value: str | None
) -> str | None:
    """Validate optional GitHub, LinkedIn, and Devpost answer URLs."""
    platform = question_label.strip().lower()
    expected_host = PROFILE_HOSTS.get(platform)
    if expected_host is None or value is None or not value.strip():
        return value

    try:
        parsed = urlsplit(value.strip())
        hostname = (parsed.hostname or "").lower()
    except ValueError as error:
        raise ValueError(f"Enter a valid {question_label} profile URL") from error

    is_expected_host = hostname in {expected_host, f"www.{expected_host}"}
    if platform != "github":
        is_expected_host = is_expected_host or hostname.endswith(
            f".{expected_host}"
        )
    has_profile_path = any(parsed.path.split("/")) or (
        platform == "devpost"
        and hostname not in {expected_host, f"www.{expected_host}"}
    )

    if (
        parsed.scheme.lower() != "https"
        or parsed.username is not None
        or parsed.password is not None
        or not is_expected_host
        or not has_profile_path
    ):
        raise ValueError(
            f"Enter a valid {question_label} profile URL on {expected_host}"
        )

    return value
