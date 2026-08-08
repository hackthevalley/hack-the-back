from pydantic import BaseModel, Field
from sqlmodel import SQLModel

from app.models.forms import FormAnswer, FormApplication


class FormAnswerUpdate(SQLModel):
    question_id: str = Field(max_length=36)
    answer: str | None = Field(None, max_length=5000)


class ApplicationResponse(BaseModel):
    application: FormApplication
    form_answers: list[FormAnswer]
    form_answer_files: str | None


class WalkInRequest(BaseModel):
    email: str = Field(max_length=255)
