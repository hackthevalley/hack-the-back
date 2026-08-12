import logging
from pathlib import Path
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from fastapi.responses import FileResponse
from sqlmodel import select

from app.config import EmailConfig
from app.core.db import SessionDep
from app.models.constants import RankingSort, SortOrder
from app.models.bulk_email import BulkEmailJob
from app.models.forms import FormApplication, StatusEnum
from app.models.user import AccountUser
from app.schemas.bulk_email import BulkEmailRequest
from app.schemas.user import UserPublic
from app.services.admin_applications import (
    get_application_detail,
    get_resume_metadata,
    list_applications as list_application_records,
    update_application_status as update_status,
)
from app.services.bulk_email import get_bulk_email_recipients, send_batch_email

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/users", response_model=list[UserPublic])
def get_users(
    session: SessionDep,
    offset: int = 0,
    limit: Annotated[int, Query(le=100)] = 100,
) -> list[UserPublic]:
    users = session.exec(select(AccountUser).offset(offset).limit(limit)).all()
    return [UserPublic.model_validate(user) for user in users]


@router.get("/applicants", response_model=list[UserPublic])
def get_applicants(
    session: SessionDep,
    offset: int = 0,
    limit: Annotated[int, Query(le=100)] = 100,
) -> list[UserPublic]:
    users = session.exec(
        select(AccountUser)
        .join(FormApplication, AccountUser.uid == FormApplication.uid)
        .offset(offset)
        .limit(limit)
    ).all()
    return [UserPublic.model_validate(user) for user in users]


@router.get("/applications/{application_id}/resume")
def get_resume(application_id: UUID, session: SessionDep) -> FileResponse:
    path, filename = get_resume_metadata(session, application_id)
    return FileResponse(path=str(path), media_type="application/pdf", filename=filename)


@router.get("/applications/{application_id}")
def get_application(application_id: UUID, session: SessionDep) -> dict[str, Any]:
    return get_application_detail(session, application_id)


@router.get("/applications")
def list_applications(
    session: SessionDep,
    offset: int = 0,
    limit: Annotated[int, Query(le=100)] = 25,
    search: Annotated[str, Query(max_length=100)] = "",
    level_of_study: Annotated[str, Query(max_length=100)] = "",
    gender: Annotated[str, Query(max_length=50)] = "",
    school: Annotated[str, Query(max_length=200)] = "",
    date_sort: SortOrder | None = None,
    ranking_sort: RankingSort | None = None,
    role: StatusEnum | None = None,
) -> dict[str, Any]:
    return list_application_records(
        session,
        offset=offset,
        limit=limit,
        search=search,
        level_of_study=level_of_study,
        gender=gender,
        school=school,
        date_sort=date_sort,
        ranking_sort=ranking_sort,
        application_status=role,
    )


@router.patch("/applications/{application_id}/status")
def update_application_status(
    application_id: str,
    request: StatusEnum,
    session: SessionDep,
    background_tasks: BackgroundTasks,
) -> dict[str, Any]:
    return update_status(session, application_id, request, background_tasks.add_task)


@router.post("/bulk-emails")
def send_bulk_email_endpoint(
    request: BulkEmailRequest,
    session: SessionDep,
    background_tasks: BackgroundTasks,
) -> dict[str, Any]:
    template = Path(request.template_path)
    if not template.exists() or not template.is_file():
        raise HTTPException(status_code=404, detail="Template file not found")

    total, recipients = get_bulk_email_recipients(session, request)
    if total == 0:
        return {
            "message": f"No users found with status: {request.status.value}",
            "total_recipients": 0,
            "status": "no_recipients",
        }
    if total > EmailConfig.BULK_WARN_THRESHOLD:
        logger.warning("Large bulk email operation: %s recipients", total)

    job = BulkEmailJob(total_recipients=total)
    session.add(job)
    session.commit()
    session.refresh(job)

    background_tasks.add_task(
        send_batch_email,
        recipients,
        request.template_path,
        request.subject,
        request.text_body,
        request.context,
        job.job_id,
    )
    return {
        "message": f"Bulk email job queued for status: {request.status.value}",
        "total_recipients": total,
        "status": "queued",
        "job_id": str(job.job_id),
        "note": "Emails are being sent concurrently in the background (chunks of 100, max 10 concurrent)",
    }


@router.get("/bulk-emails/{job_id}")
def get_bulk_email_job(job_id: UUID, session: SessionDep) -> BulkEmailJob:
    job = session.get(BulkEmailJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Bulk email job not found")
    return job
