from datetime import datetime, timedelta, timezone

import pytest

from app.cache import SimpleCache
from app import validators


def test_cache_lifecycle_and_expiry():
    cache = SimpleCache()
    assert cache.get("missing") is None
    cache.set("key", "value")
    assert cache.get("key") == "value"
    assert cache.get_or_set("key", lambda: "other") == "value"
    cache.delete("key")
    assert cache.get("key") is None

    cache.set("expired", 1, timedelta(seconds=-1))
    assert cache.get("expired") is None
    assert cache.get_or_set("new", lambda: 2, timedelta(minutes=1)) == 2

    cache.set("old", 3, timedelta(seconds=-1))
    cache._last_cleanup = datetime.now(timezone.utc) - timedelta(minutes=6)
    cache.set("current", 4)
    assert "old" not in cache._cache
    cache.clear()
    assert cache._cache == {}


@pytest.mark.parametrize(
    ("password", "message"),
    [
        ("Short1", "at least"),
        ("lowercase1", "uppercase"),
        ("UPPERCASE1", "lowercase"),
        ("NoDigitsHere", "number"),
    ],
)
def test_password_validation_failures(password, message):
    with pytest.raises(ValueError, match=message):
        validators.validate_password_requirements(password)


def test_password_validation_success_and_optional_special(monkeypatch):
    assert validators.validate_password_requirements("GoodPassword1") == "GoodPassword1"
    monkeypatch.setattr(validators, "PASSWORD_REQUIRE_SPECIAL", True)
    with pytest.raises(ValueError, match="special character"):
        validators.validate_password_requirements("GoodPassword1")
    assert validators.validate_password_requirements("GoodPassword1!") == "GoodPassword1!"


@pytest.mark.parametrize(
    ("label", "url"),
    [
        ("Github", "https://github.com/hackthevalley"),
        ("LinkedIn", "https://www.linkedin.com/in/hackthevalley"),
        ("LinkedIn", "https://ca.linkedin.com/in/hackthevalley"),
        ("Devpost", "https://hackthevalley.devpost.com"),
        ("Devpost", "https://devpost.com/hackthevalley"),
    ],
)
def test_profile_url_validation_success(label, url):
    assert validators.validate_profile_url(label, url) == url


@pytest.mark.parametrize(
    ("label", "url"),
    [
        ("Github", "http://github.com/hackthevalley"),
        ("Github", "https://gitlab.com/hackthevalley"),
        ("Github", "https://github.com"),
        ("LinkedIn", "not-a-url"),
        ("LinkedIn", "https://linkedin.example.com/in/hackthevalley"),
        ("Devpost", "https://devpost.com"),
        ("Devpost", "https://user:password@devpost.com/hackthevalley"),
    ],
)
def test_profile_url_validation_failure(label, url):
    with pytest.raises(ValueError, match="valid"):
        validators.validate_profile_url(label, url)


def test_profile_url_validation_allows_optional_and_unrelated_answers():
    assert validators.validate_profile_url("Github", "") == ""
    assert validators.validate_profile_url("LinkedIn", None) is None
    assert validators.validate_profile_url("School Name", "Example University") == (
        "Example University"
    )


@pytest.mark.parametrize(
    ("label", "answer"),
    [
        ("Country", "Canada"),
        ("School Name", "University of Toronto (Scarborough)"),
        ("Expected Graduation Year", "2027"),
        ("Age", "18"),
        ("Hackathon Count?", "0"),
        ("Phone Number", "+1 (416) 555-1234"),
        ("Race/Ethnicity (Select all that apply)", '["Other"]'),
        ("Avatar", "owl"),
        ("Accessory", "hat"),
        ("UI/UX Design", "Beginner"),
        ("MLH Event Communication", "false"),
        ("Portfolio", "https://example.com/portfolio"),
    ],
)
def test_form_answer_validation_accepts_frontend_values(label, answer):
    assert validators.validate_form_answer(label, answer) == answer


@pytest.mark.parametrize(
    ("label", "answer"),
    [
        ("Country", "Answer 1"),
        ("School Name", "Answer 1"),
        ("Expected Graduation Year", "Answer 1"),
        ("Age", "0"),
        ("Hackathon Count?", "-1"),
        ("Phone Number", "Answer 1"),
        ("Race/Ethnicity (Select all that apply)", '["Answer 1"]'),
        ("Race/Ethnicity (Select all that apply)", '{"Other": true}'),
        ("Avatar", "Answer 1"),
        ("Accessory", "Answer 1"),
        ("Frontend Development", "Answer 1"),
        ("MLH Code of Conduct", "Answer 1"),
        ("Portfolio", "not a URL"),
    ],
)
def test_form_answer_validation_rejects_api_only_values(label, answer):
    with pytest.raises(ValueError):
        validators.validate_form_answer(label, answer)


def test_form_answer_validation_allows_empty_draft_values():
    assert validators.validate_form_answer("Country", "") == ""
    assert validators.validate_form_answer("Country", None) is None
