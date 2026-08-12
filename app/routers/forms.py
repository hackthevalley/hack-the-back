from datetime import timedelta
from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends, UploadFile, status
from sqlmodel import col, select

from app.cache import cache
from app.core.db import SessionDep
from app.models.forms import FormQuestion, FormWindow
from app.models.user import AccountUser
from app.schemas.forms import ApplicationResponse, FormAnswerUpdate
from app.services.applications import is_valid_submission_time
from app.dependencies.auth import get_current_user
from app.services.form_workflow import (
    get_or_create_application,
    save_answers as save_application_answers,
    submit_application,
)
from app.services.resume_uploads import upload_resume as store_resume

router = APIRouter()


@router.get("/questions")
def get_questions(session: SessionDep) -> list[FormQuestion]:
    def fetch_questions() -> list[FormQuestion]:
        return list(
            session.exec(
                select(FormQuestion).order_by(col(FormQuestion.question_order))
            ).all()
        )

    return cache.get_or_set("form_questions", fetch_questions, timedelta(minutes=10))


@router.get("/application", response_model=ApplicationResponse)
def get_application(
    current_user: Annotated[AccountUser, Depends(get_current_user)],
    session: SessionDep,
) -> dict[str, Any]:
    return get_or_create_application(session, current_user)


@router.put("/answers")
def save_answers(
    forms_batchupdate: list[FormAnswerUpdate],
    current_user: Annotated[AccountUser, Depends(get_current_user)],
    session: SessionDep,
) -> dict[str, Any]:
    return save_application_answers(session, current_user, forms_batchupdate)


@router.post("/resume")
def upload_resume(
    file: UploadFile,
    current_user: Annotated[AccountUser, Depends(get_current_user)],
    session: SessionDep,
) -> str:
    return store_resume(session, current_user, file)


@router.post("/submission", status_code=status.HTTP_201_CREATED)
def submit(
    current_user: Annotated[AccountUser, Depends(get_current_user)],
    session: SessionDep,
    background_tasks: BackgroundTasks,
) -> str:
    return submit_application(session, current_user, background_tasks.add_task)


@router.get("/submission-time")
def submission_time(session: SessionDep) -> bool:
    return is_valid_submission_time(session)


@router.get("/registration-timerange", response_model=FormWindow)
def get_reg_time_range(session: SessionDep) -> FormWindow:
    def fetch_time_range() -> FormWindow | None:
        return session.exec(select(FormWindow)).first()

    return cache.get_or_set(
        "registration_timerange", fetch_time_range, timedelta(minutes=5)
    )
