import uuid
from datetime import datetime, timezone

from typing import ClassVar

from sqlmodel import Column, DateTime, Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class JudgingApplicationScore(SQLModel, table=True):
    __tablename__: ClassVar[str] = "judging_application_score"

    application_id: uuid.UUID = Field(
        primary_key=True,
        foreign_key="forms_application.application_id",
    )
    mu: float = Field(default=0.0, nullable=False, index=True)
    sigma_sq: float = Field(default=1.0, nullable=False)
    comparison_count: int = Field(default=0, nullable=False)
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class JudgingJudgeState(SQLModel, table=True):
    __tablename__: ClassVar[str] = "judging_judge_state"

    judge_id: uuid.UUID = Field(primary_key=True, foreign_key="account_user.uid")
    alpha: float = Field(default=10.0, nullable=False)
    beta: float = Field(default=1.0, nullable=False)
    left_application_id: uuid.UUID | None = Field(
        default=None, foreign_key="forms_application.application_id"
    )
    right_application_id: uuid.UUID | None = Field(
        default=None, foreign_key="forms_application.application_id"
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False, index=True),
    )


class JudgingDecision(SQLModel, table=True):
    __tablename__: ClassVar[str] = "judging_decision"

    decision_id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    request_id: uuid.UUID = Field(unique=True)
    judge_id: uuid.UUID = Field(index=True, foreign_key="account_user.uid")
    winner_application_id: uuid.UUID = Field(
        index=True, foreign_key="forms_application.application_id"
    )
    loser_application_id: uuid.UUID = Field(
        index=True, foreign_key="forms_application.application_id"
    )
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
