from urllib.parse import urlsplit


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


PROFILE_HOSTS = {
    "github": "github.com",
    "linkedin": "linkedin.com",
    "devpost": "devpost.com",
}


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
