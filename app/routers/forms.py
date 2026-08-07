from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, UploadFile, status
from sqlmodel import col, select

from app.cache import cache
from app.core.db import SessionDep
from app.models.forms import (
    ApplicationResponse,
    Forms_AnswerUpdate,
    Forms_Form,
    Forms_Question,
)
from app.models.user import AccountUser
from app.services.applications import is_valid_submission_time
from app.services.auth import get_current_user
from app.services.form_workflow import (
    get_or_create_application,
    save_answers as save_application_answers,
    submit_application,
)
from app.services.resume_uploads import upload_resume as store_resume
from app.services.resume_uploads import validate_pdf

router = APIRouter()

# Kept as a private alias for compatibility with existing imports.
_validate_pdf = validate_pdf


@router.get("/questions")
def get_questions(session: SessionDep) -> list[Forms_Question]:
    def fetch_questions() -> list[Forms_Question]:
        return list(
            session.exec(
                select(Forms_Question).order_by(col(Forms_Question.question_order))
            ).all()
        )

    return cache.get_or_set(
        "form_questions", fetch_questions, timedelta(minutes=10)
    )


@router.get("/application", response_model=ApplicationResponse)
def get_application(
    current_user: Annotated[AccountUser, Depends(get_current_user)],
    session: SessionDep,
):
    return get_or_create_application(session, current_user)


@router.put("/answers")
def save_answers(
    forms_batchupdate: list[Forms_AnswerUpdate],
    current_user: Annotated[AccountUser, Depends(get_current_user)],
    session: SessionDep,
):
    return save_application_answers(session, current_user, forms_batchupdate)


@router.post("/resume")
def upload_resume(
    file: UploadFile,
    current_user: Annotated[AccountUser, Depends(get_current_user)],
    session: SessionDep,
):
    return store_resume(session, current_user, file)


@router.post("/submission", status_code=status.HTTP_201_CREATED)
def submit(
    current_user: Annotated[AccountUser, Depends(get_current_user)],
    session: SessionDep,
):
    return submit_application(session, current_user)


@router.get("/submission-time")
def submission_time(session: SessionDep):
    return is_valid_submission_time(session)


@router.get("/registration-timerange", response_model=Forms_Form)
def get_reg_time_range(session: SessionDep) -> Forms_Form:
    def fetch_time_range():
        return session.exec(select(Forms_Form)).first()

    return cache.get_or_set(
        "registration_timerange", fetch_time_range, timedelta(minutes=5)
    )
