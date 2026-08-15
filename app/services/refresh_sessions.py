import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import update
from sqlmodel import Session, col, select

from app.config import SecurityConfig
from app.core.errors import ServiceError
from app.models.refresh_session import RefreshSession
from app.models.user import AccountUser


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _new_token() -> str:
    return secrets.token_urlsafe(48)


def create_refresh_session(
    session: Session, user: AccountUser
) -> tuple[RefreshSession, str]:
    now = datetime.now(timezone.utc)
    raw_token = _new_token()
    refresh_session = RefreshSession(
        user_id=user.uid,
        token_hash=_hash_token(raw_token),
        token_version=user.token_version,
        created_at=now,
        last_used_at=now,
        expires_at=now + timedelta(days=SecurityConfig.REFRESH_TOKEN_EXPIRE_DAYS),
    )
    session.add(refresh_session)
    return refresh_session, raw_token


def _revoke_family(
    session: Session, family_id: uuid.UUID, revoked_at: datetime
) -> None:
    session.exec(
        update(RefreshSession)
        .where(
            RefreshSession.family_id == family_id,
            col(RefreshSession.revoked_at).is_(None),
        )
        .values(revoked_at=revoked_at)
    )


def rotate_refresh_session(session: Session, raw_token: str) -> tuple[AccountUser, str]:
    now = datetime.now(timezone.utc)
    current = session.exec(
        select(RefreshSession)
        .where(RefreshSession.token_hash == _hash_token(raw_token))
        .with_for_update()
    ).first()
    if current is None:
        raise ServiceError(status_code=401, detail="Invalid refresh token")

    if current.revoked_at is not None:
        _revoke_family(session, current.family_id, now)
        session.commit()
        raise ServiceError(status_code=401, detail="Refresh token reuse detected")

    user = session.get(AccountUser, current.user_id)
    idle_deadline = current.last_used_at + timedelta(
        days=SecurityConfig.REFRESH_TOKEN_IDLE_DAYS
    )
    if (
        user is None
        or not user.is_active
        or user.token_version != current.token_version
        or now >= current.expires_at
        or now >= idle_deadline
    ):
        _revoke_family(session, current.family_id, now)
        session.commit()
        raise ServiceError(status_code=401, detail="Refresh session expired")

    replacement, replacement_token = create_refresh_session(session, user)
    replacement.family_id = current.family_id
    session.flush()
    current.last_used_at = now
    current.revoked_at = now
    current.replaced_by_id = replacement.session_id
    session.add(current)
    session.add(replacement)
    session.commit()
    return user, replacement_token


def revoke_refresh_session(session: Session, raw_token: str | None) -> None:
    if not raw_token:
        return
    current = session.exec(
        select(RefreshSession).where(
            RefreshSession.token_hash == _hash_token(raw_token)
        )
    ).first()
    if current is None:
        return
    _revoke_family(session, current.family_id, datetime.now(timezone.utc))
    session.commit()
