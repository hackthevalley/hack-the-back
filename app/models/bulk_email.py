import uuid
from datetime import datetime, timezone
from typing import ClassVar

from sqlmodel import Column, DateTime, Field, SQLModel


class BulkEmailJob(SQLModel, table=True):
    __tablename__: ClassVar[str] = "bulk_email_job"

    job_id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    status: str = Field(default="queued", index=True, max_length=20)
    total_recipients: int = 0
    successful: int = 0
    failed: int = 0
    error_summary: str | None = Field(default=None, max_length=2000)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    completed_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
