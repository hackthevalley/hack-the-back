import uuid
from datetime import datetime, timezone
from typing import ClassVar

from sqlmodel import Column, DateTime, Field, SQLModel, String


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class RefreshSession(SQLModel, table=True):
    __tablename__: ClassVar[str] = "account_refresh_session"

    session_id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(
        foreign_key="account_user.uid", ondelete="CASCADE", index=True
    )
    family_id: uuid.UUID = Field(default_factory=uuid.uuid4, index=True)
    token_hash: str = Field(
        sa_column=Column(String(64), nullable=False, unique=True, index=True)
    )
    token_version: int = Field(nullable=False)
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    last_used_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    expires_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    revoked_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    replaced_by_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="account_refresh_session.session_id",
        ondelete="SET NULL",
    )
