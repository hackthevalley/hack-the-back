import uuid
from datetime import datetime, timezone
from typing import ClassVar

from sqlmodel import Column, DateTime, Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ScheduleEvent(SQLModel, table=True):
    __tablename__: ClassVar[str] = "schedule_event"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    title: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    location: str | None = Field(default=None, max_length=160)
    starts_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False, index=True)
    )
    ends_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False, index=True)
    )
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
