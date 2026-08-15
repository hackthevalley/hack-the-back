from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.core.errors import ServiceError
from app.models.refresh_session import RefreshSession
from app.services import refresh_sessions


def result(*, first=None):
    return SimpleNamespace(first=lambda: first)


def user():
    return SimpleNamespace(uid=uuid4(), token_version=3, is_active=True)


def stored_session(account, **updates):
    now = datetime.now(timezone.utc)
    values = {
        "user_id": account.uid,
        "family_id": uuid4(),
        "token_hash": "a" * 64,
        "token_version": account.token_version,
        "created_at": now,
        "last_used_at": now,
        "expires_at": now + timedelta(days=30),
    }
    values.update(updates)
    return RefreshSession(**values)


def test_create_refresh_session_hashes_token_and_sets_expiry():
    session = MagicMock()
    account = user()

    with patch.object(refresh_sessions, "_new_token", return_value="raw-secret"):
        created, raw_token = refresh_sessions.create_refresh_session(session, account)

    assert raw_token == "raw-secret"
    assert created.token_hash != raw_token
    assert created.token_hash == refresh_sessions._hash_token(raw_token)
    assert created.user_id == account.uid
    assert created.token_version == account.token_version
    assert created.expires_at > created.created_at
    session.add.assert_called_once_with(created)


def test_rotate_rejects_unknown_token():
    session = MagicMock()
    session.exec.return_value = result(first=None)

    with pytest.raises(ServiceError, match="Invalid refresh token"):
        refresh_sessions.rotate_refresh_session(session, "missing")


def test_rotate_detects_reuse_and_revokes_family():
    session = MagicMock()
    account = user()
    current = stored_session(
        account, revoked_at=datetime.now(timezone.utc) - timedelta(seconds=1)
    )
    session.exec.side_effect = [result(first=current), MagicMock()]

    with pytest.raises(ServiceError, match="reuse detected"):
        refresh_sessions.rotate_refresh_session(session, "replayed")

    session.commit.assert_called_once()


@pytest.mark.parametrize(
    "change",
    [
        {"user_missing": True},
        {"is_active": False},
        {"token_version": 4},
        {"expires_at": datetime.now(timezone.utc) - timedelta(seconds=1)},
        {"last_used_at": datetime.now(timezone.utc) - timedelta(days=8)},
    ],
)
def test_rotate_rejects_invalid_or_expired_session(change):
    session = MagicMock()
    account = user()
    current_updates = {
        key: value
        for key, value in change.items()
        if key in {"expires_at", "last_used_at"}
    }
    current = stored_session(account, **current_updates)
    if "is_active" in change:
        account.is_active = change["is_active"]
    if "token_version" in change:
        account.token_version = change["token_version"]
    session.exec.side_effect = [result(first=current), MagicMock()]
    session.get.return_value = None if change.get("user_missing") else account

    with pytest.raises(ServiceError, match="expired"):
        refresh_sessions.rotate_refresh_session(session, "expired")

    session.commit.assert_called_once()


def test_rotate_replaces_valid_token():
    session = MagicMock()
    account = user()
    current = stored_session(account)
    replacement = stored_session(account, family_id=uuid4())
    session.exec.return_value = result(first=current)
    session.get.return_value = account

    with patch.object(
        refresh_sessions,
        "create_refresh_session",
        return_value=(replacement, "replacement-secret"),
    ):
        returned_user, raw_token = refresh_sessions.rotate_refresh_session(
            session, "current-secret"
        )

    assert returned_user is account
    assert raw_token == "replacement-secret"
    assert replacement.family_id == current.family_id
    assert current.revoked_at is not None
    assert current.replaced_by_id == replacement.session_id
    session.commit.assert_called_once()


def test_revoke_handles_absent_unknown_and_valid_tokens():
    session = MagicMock()
    refresh_sessions.revoke_refresh_session(session, None)
    session.exec.assert_not_called()

    session.exec.return_value = result(first=None)
    refresh_sessions.revoke_refresh_session(session, "unknown")
    session.commit.assert_not_called()

    account = user()
    current = stored_session(account)
    session.exec.side_effect = [result(first=current), MagicMock()]
    refresh_sessions.revoke_refresh_session(session, "valid")
    session.commit.assert_called_once()
