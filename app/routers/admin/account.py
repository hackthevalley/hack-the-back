import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import aliased, selectinload
from sqlmodel import select

from app.core.db import SessionDep
from app.models.constants import QuestionLabel, SortOrder
from app.models.forms import (
    Forms_Answer,
    Forms_AnswerFile,
    Forms_Application,
    Forms_HackathonApplicant,
    Forms_Question,
    StatusEnum,
)
from app.models.requests import BulkEmailRequest
from app.models.user import Account_User, UserPublic
from app.utils import sendEmail

router = APIRouter()
logger = logging.getLogger(__name__)


def _sanitize_filename(filename: str) -> str:
    """
    Sanitize filename to prevent path traversal attacks.

    Removes directory traversal sequences and dangerous characters.
    Ensures the filename is safe for use in Content-Disposition header.

    Args:
        filename: User-provided filename

    Returns:
        Sanitized filename safe for use
    """
    import re

    filename = Path(filename).name

    filename = filename.replace("\x00", "")

    filename = filename.replace("..", "")
    filename = filename.replace("./", "")
    filename = filename.replace("../", "")

    filename = re.sub(r"[^\w\s\-.]", "", filename)

    filename = filename.lstrip(".")

    max_length = 255
    if len(filename) > max_length:
        name_parts = filename.rsplit(".", 1)
        if len(name_parts) == 2:
            name, ext = name_parts
            filename = name[: max_length - len(ext) - 1] + "." + ext
        else:
            filename = filename[:max_length]

    if not filename or filename.isspace():
        filename = "file.pdf"

    return filename


async def send_batch_email(
    users_data: list[dict],
    template_path: str,
    subject: str,
    text_body: str,
    base_context: dict,
):
    """
    Send emails to multiple users concurrently with proper error tracking.

    Uses asyncio.gather with semaphore to limit concurrent operations.
    Processes in chunks to balance memory usage and throughput.

    Configuration (via environment variables):
        BULK_EMAIL_CHUNK_SIZE: Number of emails per chunk (default: 100)
        BULK_EMAIL_MAX_CONCURRENT: Max concurrent email sends (default: 10)
    """
    import asyncio

    from app.config import EmailConfig

    total = len(users_data)
    successful = 0
    failed = 0
    failures = []

    MAX_CONCURRENT = EmailConfig.BULK_MAX_CONCURRENT
    CHUNK_SIZE = EmailConfig.BULK_CHUNK_SIZE

    logger.info(
        f"Starting bulk email send: {total} recipients, subject='{subject}', "
        f"template='{template_path}', concurrency={MAX_CONCURRENT}, chunk_size={CHUNK_SIZE}"
    )

    semaphore = asyncio.Semaphore(MAX_CONCURRENT)

    async def send_with_semaphore(user_data: dict) -> tuple[bool, str, dict]:
        """Send email with rate limiting via semaphore. Uses sendEmail from utils."""
        email = user_data.get("email", "unknown")
        async with semaphore:
            try:
                email_context = base_context.copy() if base_context else {}
                email_context.update(user_data)

                status_code, response = await sendEmail(
                    template_path,
                    email,
                    subject,
                    text_body,
                    email_context,
                )

                if status_code == 200:
                    return (True, email, {})
                else:
                    return (
                        False,
                        email,
                        {
                            "email": email,
                            "reason": f"Status {status_code}",
                            "response": response,
                        },
                    )
            except Exception as e:
                return (False, email, {"email": email, "reason": str(e)})

    for i in range(0, total, CHUNK_SIZE):
        chunk = users_data[i : i + CHUNK_SIZE]
        chunk_num = (i // CHUNK_SIZE) + 1
        total_chunks = (total + CHUNK_SIZE - 1) // CHUNK_SIZE

        logger.info(
            f"Processing chunk {chunk_num}/{total_chunks} ({len(chunk)} emails)"
        )

        results = await asyncio.gather(
            *[send_with_semaphore(user_data) for user_data in chunk],
            return_exceptions=False,
        )

        for success, email, error_info in results:
            if success:
                successful += 1
                logger.debug(f"Email sent successfully to {email}")
            else:
                failed += 1
                failures.append(error_info)
                logger.warning(
                    f"Email send failed to {email}: {error_info.get('reason')}"
                )

    logger.info(
        f"Bulk email send complete: {successful}/{total} successful, {failed}/{total} failed"
    )

    if failures:
        logger.warning(f"Failed emails summary: {failures[:10]}")


@router.get("/users", response_model=list[UserPublic])
def get_users(
    session: SessionDep,
    offset: int = 0,
    limit: Annotated[int, Query(le=100)] = 100,
) -> list[UserPublic]:
    users = session.exec(select(Account_User).offset(offset).limit(limit)).all()
    return users


@router.get("/applicants")
def getapplicants(
    session: SessionDep,
    offset: int = 0,
    limit: Annotated[int, Query(le=100)] = 100,
):
    applicants = session.exec(
        select(Account_User)
        .offset(offset)
        .limit(limit)
        .where(Account_User.application.application_id is not None)
    ).all()
    return applicants


@router.get("/applications/{application_id}/resume")
def get_resume(
    application_id: UUID,
    session: SessionDep,
):
    statement = select(Forms_AnswerFile).where(
        Forms_AnswerFile.application_id == application_id
    )
    resume = session.exec(statement).first()

    if not resume or not resume.file_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found"
        )

    file_path = Path(resume.file_path)
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="File not found on disk"
        )

    safe_filename = _sanitize_filename(resume.original_filename or "resume.pdf")

    return FileResponse(
        path=str(file_path),
        media_type="application/pdf",
        filename=safe_filename,
    )


@router.get("/applications/{application_id}")
def get_application(application_id: UUID, session: SessionDep):
    statement = select(Forms_Application).where(
        Forms_Application.application_id == application_id
    )
    application = session.exec(statement).first()
    if application is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Application not found"
        )
    return {
        "application": application,
        "form_answers": application.form_answers,
        "form_answersfile": application.form_answersfile.original_filename
        if application.form_answersfile
        else None,
    }


@router.get("/applications")
async def get_all_apps(
    session: SessionDep,
    ofs: int = 0,
    limit: Annotated[int, Query(le=100)] = 25,
    search: Annotated[str, Query(max_length=100)] = "",
    level_of_study: Annotated[str, Query(max_length=100)] = "",
    gender: Annotated[str, Query(max_length=50)] = "",
    school: Annotated[str, Query(max_length=200)] = "",
    date_sort: SortOrder | None = None,
    role: StatusEnum | None = None,
):
    from datetime import timedelta

    from app.cache import cache

    def fetch_questions():
        questions_statement = select(Forms_Question).where(
            Forms_Question.label.in_(
                [
                    QuestionLabel.CURRENT_LEVEL_OF_STUDY.value,
                    QuestionLabel.GENDER.value,
                    QuestionLabel.SCHOOL_NAME.value,
                ]
            )
        )
        questions = session.exec(questions_statement).all()
        return {q.label: q for q in questions}

    question_map = cache.get_or_set(
        key="admin_filter_questions",
        factory_func=fetch_questions,
        ttl=timedelta(minutes=10),
    )

    level_of_study_question = question_map.get(
        QuestionLabel.CURRENT_LEVEL_OF_STUDY.value
    )
    gender_question = question_map.get(QuestionLabel.GENDER.value)
    school_question = question_map.get(QuestionLabel.SCHOOL_NAME.value)

    level_of_study_data = aliased(Forms_Answer)
    gender_data = aliased(Forms_Answer)
    school_data = aliased(Forms_Answer)

    statement = (
        select(
            Account_User,
            Forms_Application,
            Forms_HackathonApplicant,
            level_of_study_data.answer.label("level_of_study_answer"),
            gender_data.answer.label("gender_answer"),
            school_data.answer.label("school_answer"),
        )
        .where(
            Account_User.is_active,
            Account_User.application is not None,
        )
        .join(Forms_Application, Account_User.uid == Forms_Application.uid)
        .join(
            Forms_HackathonApplicant,
            Forms_Application.application_id == Forms_HackathonApplicant.application_id,
        )
    )

    if level_of_study_question:
        statement = statement.outerjoin(
            level_of_study_data,
            and_(
                level_of_study_data.application_id == Forms_Application.application_id,
                level_of_study_data.question_id == level_of_study_question.question_id,
            ),
        )

    if gender_question:
        statement = statement.outerjoin(
            gender_data,
            and_(
                gender_data.application_id == Forms_Application.application_id,
                gender_data.question_id == gender_question.question_id,
            ),
        )

    if school_question:
        statement = statement.outerjoin(
            school_data,
            and_(
                school_data.application_id == Forms_Application.application_id,
                school_data.question_id == school_question.question_id,
            ),
        )

    if search:
        search_pattern = f"%{search}%"
        statement = statement.where(
            or_(
                Account_User.first_name.ilike(search_pattern),
                Account_User.last_name.ilike(search_pattern),
                Account_User.email.ilike(search_pattern),
                (Account_User.first_name + " " + Account_User.last_name).ilike(
                    search_pattern
                ),
            )
        )

    if role:
        statement = statement.where(Forms_HackathonApplicant.status == role)

    if level_of_study and level_of_study_question:
        statement = statement.where(
            func.lower(level_of_study_data.answer) == level_of_study.lower()
        )

    if gender and gender_question:
        statement = statement.where(func.lower(gender_data.answer) == gender.lower())

    if school and school_question:
        statement = statement.where(
            and_(
                school_data.answer.isnot(None),
                school_data.answer != "",
                func.lower(school_data.answer) == school.lower(),
            )
        )

    if date_sort:
        if date_sort == SortOrder.OLDEST:
            statement = statement.order_by(Forms_Application.updated_at.asc())
        elif date_sort == SortOrder.LATEST:
            statement = statement.order_by(Forms_Application.updated_at.desc())

    statement = statement.offset(ofs).limit(limit)

    results = session.exec(statement).all()

    response = [
        {
            "first_name": user.first_name,
            "last_name": user.last_name,
            "email": user.email,
            "status": hacker_applicant.status,
            "app_id": hacker_applicant.application_id,
            "created_at": user_app.created_at,
            "updated_at": user_app.updated_at,
            "level_of_study": level_study,
            "gender": gender_val,
            "school": school_val,
        }
        for (
            user,
            user_app,
            hacker_applicant,
            level_study,
            gender_val,
            school_val,
        ) in results
    ]

    return {"application": response, "offset": ofs, "limit": limit}


@router.patch("/applications/{application_id}/status")
async def update_application_status(
    application_id: str, request: StatusEnum, session: SessionDep
):
    statement = (
        select(Forms_Application, Account_User)
        .join(Account_User, Forms_Application.uid == Account_User.uid)
        .where(Forms_Application.application_id == application_id)
        .options(selectinload(Forms_Application.hackathonapplicant))
    )
    result = session.exec(statement).first()

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Application not found"
        )

    application, user = result

    try:
        application.hackathonapplicant.status = request.value
        application.updated_at = datetime.now(timezone.utc)

        session.add(application.hackathonapplicant)
        session.add(application)
        session.commit()
        session.refresh(application.hackathonapplicant)
        session.refresh(application)

        if request == StatusEnum.ACCEPTED:
            from app.utils import send_rsvp

            user_full_name = user.full_name
            await send_rsvp(user.email, user_full_name, application_id)

    except Exception as e:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update application status: {str(e)}",
        )

    return {
        "application_id": application_id,
        "new_status": request.value,
        "updated_at": application.updated_at,
    }


@router.post("/bulk-emails")
async def send_bulk_email_endpoint(
    request: BulkEmailRequest, session: SessionDep, background_tasks: BackgroundTasks
):
    """
    Send an email to all applicants with a specific status.

    Emails are sent asynchronously in the background using concurrent processing.
    Large datasets are chunked to balance memory usage and throughput.

    Args:
        template_path: Path to the email template (e.g., "templates/hacker_package.html")
        status: The application status to filter by (e.g., "ACCEPTED_INVITE")
        subject: Email subject line
        text_body: Plain text version of the email
        context: Optional dict of template variables to pass to the template

    Returns:
        Confirmation that the email job has been queued
    """
    template_file = Path(request.template_path)
    if not template_file.exists() or not template_file.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Template file not found"
        )

    count_statement = (
        select(func.count())
        .select_from(Account_User)
        .join(Forms_Application, Account_User.uid == Forms_Application.uid)
        .join(
            Forms_HackathonApplicant,
            Forms_Application.application_id == Forms_HackathonApplicant.application_id,
        )
        .where(
            Account_User.is_active,
            Forms_HackathonApplicant.status == request.status,
        )
    )

    total_recipients = session.exec(count_statement).one()

    if total_recipients == 0:
        return {
            "message": f"No users found with status: {request.status.value}",
            "total_recipients": 0,
            "status": "no_recipients",
        }

    from app.config import EmailConfig

    if total_recipients > EmailConfig.BULK_WARN_THRESHOLD:
        logger.warning(
            f"Large bulk email operation: {total_recipients} recipients. "
            "Consider using a dedicated task queue (Celery/RQ) for production."
        )

    statement = (
        select(
            Account_User.first_name,
            Account_User.last_name,
            Account_User.email,
        )
        .join(Forms_Application, Account_User.uid == Forms_Application.uid)
        .join(
            Forms_HackathonApplicant,
            Forms_Application.application_id == Forms_HackathonApplicant.application_id,
        )
        .where(
            Account_User.is_active,
            Forms_HackathonApplicant.status == request.status,
        )
    )

    results = session.exec(statement).all()

    users_data = [
        {
            "first_name": row[0],
            "last_name": row[1],
            "email": row[2],
        }
        for row in results
    ]

    background_tasks.add_task(
        send_batch_email,
        users_data,
        request.template_path,
        request.subject,
        request.text_body,
        request.context,
    )

    return {
        "message": f"Bulk email job queued for status: {request.status.value}",
        "total_recipients": total_recipients,
        "status": "queued",
        "note": "Emails are being sent concurrently in the background (chunks of 100, max 10 concurrent)",
    }
