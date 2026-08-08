import uuid
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, ClassVar, Optional

from pydantic import BaseModel
from sqlmodel import Column, DateTime, Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.models.user import AccountUser


class StatusEnum(str, Enum):
    ACCOUNT_INACTIVE = "ACCOUNT_INACTIVE"
    NOT_APPLIED = "NOT_APPLIED"
    APPLYING = "APPLYING"
    APPLIED = "APPLIED"
    UNDER_REVIEW = "UNDER_REVIEW"
    WAITLISTED = "WAITLISTED"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    ACCEPTED_INVITE = "ACCEPTED_INVITE"
    REJECTED_INVITE = "REJECTED_INVITE"
    SCANNED_IN = "SCANNED_IN"
    WALK_IN = "WALK_IN"
    WALK_IN_SUBMITTED = "WALK_IN_SUBMITTED"


class FormWindow(SQLModel, table=True):
    __tablename__: ClassVar[str] = "forms_form"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    updated_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    start_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    end_at: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))


class FormApplication(SQLModel, table=True):
    __tablename__: ClassVar[str] = "forms_application"

    uid: uuid.UUID | None = Field(
        default=None,
        primary_key=True,
        foreign_key="account_user.uid",
    )
    is_draft: bool
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    updated_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    application_id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        index=True,
        unique=True,
    )
    user: Optional["AccountUser"] = Relationship(back_populates="application")
    form_answers: list["FormAnswer"] = Relationship(
        back_populates="applicant"
    )
    hackathonapplicant: Optional["HackathonApplicant"] = Relationship(
        back_populates="applicant"
    )
    form_answersfile: Optional["FormAnswerFile"] = Relationship(
        back_populates="applicant"
    )


class HackathonApplicant(SQLModel, table=True):
    __tablename__: ClassVar[str] = "forms_hackathonapplicant"

    application_id: uuid.UUID | None = Field(
        default=None, primary_key=True, foreign_key="forms_application.application_id"
    )
    status: StatusEnum = Field(index=True)
    applicant: Optional["FormApplication"] = Relationship(
        back_populates="hackathonapplicant"
    )

    def can_scan_in(self) -> bool:
        return self.status in [
            StatusEnum.ACCEPTED,
            StatusEnum.ACCEPTED_INVITE,
            StatusEnum.SCANNED_IN,
            StatusEnum.WALK_IN,
            StatusEnum.WALK_IN_SUBMITTED,
        ]

    def can_submit_application(self) -> bool:
        return self.status in [StatusEnum.APPLYING, StatusEnum.WALK_IN]

    def is_already_submitted(self) -> bool:
        return self.status in [StatusEnum.APPLIED, StatusEnum.WALK_IN_SUBMITTED]


class FormQuestion(SQLModel, table=True):
    __tablename__: ClassVar[str] = "forms_question"

    question_id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    question_order: int = Field(index=True, ge=0)
    label: str = Field(index=True, max_length=255)
    required: bool


class FormAnswer(SQLModel, table=True):
    __tablename__: ClassVar[str] = "forms_answer"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    application_id: uuid.UUID | None = Field(
        default=None, index=True, foreign_key="forms_application.application_id"
    )
    question_id: uuid.UUID = Field(index=True, foreign_key="forms_question.question_id")
    answer: str | None = Field(None, max_length=5000)
    applicant: Optional["FormApplication"] = Relationship(
        back_populates="form_answers"
    )


class FormAnswerUpdate(SQLModel):
    question_id: str = Field(max_length=36)
    answer: str | None = Field(None, max_length=5000)


class FormAnswerFile(SQLModel, table=True):
    __tablename__: ClassVar[str] = "forms_answerfile"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    application_id: uuid.UUID | None = Field(
        default=None, index=True, foreign_key="forms_application.application_id"
    )
    original_filename: Optional[str] = Field(None, max_length=255)
    file_path: Optional[str] = Field(None, max_length=500)
    question_id: uuid.UUID = Field(index=True, foreign_key="forms_question.question_id")
    applicant: Optional["FormApplication"] = Relationship(
        back_populates="form_answersfile"
    )


class ApplicationResponse(BaseModel):
    application: FormApplication
    form_answers: list[FormAnswer]
    form_answersfile: str | None


class WalkInRequest(BaseModel):
    email: str = Field(max_length=255)
