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
