import io
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import String, and_, cast, func, or_
from sqlalchemy.orm import aliased
from sqlmodel import select

from app.core.db import SessionDep
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
from app.utils import createQRCode, generate_google_wallet_pass, sendEmail

router = APIRouter()


@router.get("/users", response_model=list[UserPublic])
def get_users(
    session: SessionDep,
    offset: int = 0,
    limit: Annotated[int, Query(le=100)] = 100,
) -> list[UserPublic]:
    users = session.exec(select(Account_User).offset(offset).limit(limit)).all()
    return users


# Need to improve with search query instead of with just offsets
@router.get("/applicants")
async def getapplicants(
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
async def get_resume(
    application_id: UUID,
    session: SessionDep,
):
    # Fetch the file entry for this application
    statement = select(Forms_AnswerFile).where(
        Forms_AnswerFile.application_id == application_id
    )
    resume = session.exec(statement).first()

    if not resume or not resume.file_path:
        raise HTTPException(status_code=404, detail="Resume not found")

    file_path = Path(resume.file_path)
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found on disk")

    return FileResponse(
        path=str(file_path),
        media_type="application/pdf",
        filename=resume.original_filename or "resume.pdf",
    )


@router.get("/applications/{application_id}")
async def get_application(application_id: UUID, session: SessionDep):
    statement = select(Forms_Application).where(
        Forms_Application.application_id == application_id
    )
    application = session.exec(statement).first()
    if application is None:
        raise HTTPException(status_code=404, detail="Application not found")
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
    limit: int = 25,
    search: str = "",
    level_of_study: str = "",
    gender: str = "",
    school: str = "",
    date_sort: str = "",
    role: str = "",
):
    # Get question IDs for level of study, gender, and school
    level_of_study_question = session.exec(
        select(Forms_Question).where(Forms_Question.label == "Current Level of Study")
    ).first()
    gender_question = session.exec(
        select(Forms_Question).where(Forms_Question.label == "Gender")
    ).first()
    school_question = session.exec(
        select(Forms_Question).where(Forms_Question.label == "School Name")
    ).first()

    # Create aliases for the Forms_Answer tables we'll join for data retrieval
    # These are separate from the filter aliases to avoid conflicts
    level_of_study_data = aliased(Forms_Answer)
    gender_data = aliased(Forms_Answer)
    school_data = aliased(Forms_Answer)

    # Build the main query - SELECT all needed columns in one query
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
            Account_User.application != None,  # noqa: E711
        )
        .join(Forms_Application, Account_User.uid == Forms_Application.uid)
        .join(
            Forms_HackathonApplicant,
            Forms_Application.application_id == Forms_HackathonApplicant.application_id,
        )
    )

    # LEFT JOIN to get level of study, gender, and school data (even if null)
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

    # Apply search filter
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

    # Apply role filter
    if role:
        statement = statement.where(
            func.lower(cast(Forms_HackathonApplicant.status, String)) == role.lower()
        )

    # Apply level of study filter
    if level_of_study and level_of_study_question:
        statement = statement.where(
            func.lower(level_of_study_data.answer) == level_of_study.lower()
        )

    # Apply gender filter
    if gender and gender_question:
        statement = statement.where(func.lower(gender_data.answer) == gender.lower())

    # Apply school filter
    if school and school_question:
        statement = statement.where(
            and_(
                school_data.answer.isnot(None),
                school_data.answer != "",
                func.lower(school_data.answer) == school.lower(),
            )
        )

    # Apply date sorting
    if date_sort:
        if date_sort == "oldest":
            statement = statement.order_by(Forms_Application.updated_at.asc())
        elif date_sort == "latest":
            statement = statement.order_by(Forms_Application.updated_at.desc())

    # Apply pagination
    statement = statement.offset(ofs).limit(limit)

    # Execute query - get all data in ONE query (no N+1 problem)
    results = session.exec(statement).all()

    # Build response from the single query result
    response = []
    for (
        user,
        user_app,
        hacker_applicant,
        level_study,
        gender_val,
        school_val,
    ) in results:
        response.append(
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
        )

    return {"application": response, "offset": ofs, "limit": limit}


@router.patch("/applications/{application_id}/status")
async def update_application_status(
    application_id: str, request: StatusEnum, session: SessionDep
):
    statement = (
        select(Forms_Application, Account_User)
        .join(Account_User, Forms_Application.uid == Account_User.uid)
        .where(Forms_Application.application_id == application_id)
    )
    result = session.exec(statement).first()

    if not result:
        raise HTTPException(status_code=404, detail="Application not found")

    application, user = result

    application.hackathonapplicant.status = request.value
    application.updated_at = datetime.now(timezone.utc)
    if request.value == "ACCEPTED":
        img = await createQRCode(application_id)
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="PNG")
        img_bytes.seek(0)
        google_link = generate_google_wallet_pass(
            f"{user.first_name} {user.last_name}", application_id
        )
        await sendEmail(
            "templates/rsvp.html",
            user.email,
            "RSVP for Hack the Valley X",
            "RSVP at hackthevalley.io",
            {
                "start_date": "October 3rd 2025",
                "end_date": "October 5th 2025",
                "due_date": "September 26th 2025",
                "apple_url": f"apple-wallet/{application_id}",
                "google_url": f"{google_link}",
            },
            attachments=[("qr_code", img_bytes, "image/png")],
        )

    session.add(application.hackathonapplicant)
    session.add(application)
    session.commit()
    session.refresh(application.hackathonapplicant)
    session.refresh(application)

    return {
        "application_id": application_id,
        "new_status": request.value,
        "updated_at": application.updated_at,
    }


@router.post("/bulk-emails")
async def send_bulk_email(request: BulkEmailRequest, session: SessionDep):
    """
    Send an email to all applicants with a specific status.

    Args:
        template_path: Path to the email template (e.g., "templates/hacker_package.html")
        status: The application status to filter by (e.g., "ACCEPTED_INVITE")
        subject: Email subject line
        text_body: Plain text version of the email
        context: Optional dict of template variables to pass to the template

    Returns:
        Summary of emails sent including success/failure counts
    """
    # Validate template exists
    template_file = Path(request.template_path)
    if not template_file.exists() or not template_file.is_file():
        raise HTTPException(status_code=404, detail="Template file not found")

    # Get all users with the specified status
    statement = (
        select(Account_User)
        .join(Forms_Application, Account_User.uid == Forms_Application.uid)
        .join(
            Forms_HackathonApplicant,
            Forms_Application.application_id == Forms_HackathonApplicant.application_id,
        )
        .where(
            Account_User.is_active == True,  # noqa: E712
            Forms_HackathonApplicant.status == request.status,
        )
    )

    users = session.exec(statement).all()

    if not users:
        return {
            "message": f"No users found with status: {request.status.value}",
            "total_recipients": 0,
            "emails_sent": 0,
            "emails_failed": 0,
            "failures": [],
        }

    emails_sent = 0
    emails_failed = 0
    failures = []

    # Send email to each user
    for user in users:
        try:
            # Add user-specific info to context if needed
            email_context = request.context.copy() if request.context else {}
            email_context.update(
                {
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "email": user.email,
                }
            )

            status_code, response = await sendEmail(
                request.template_path,
                user.email,
                request.subject,
                request.text_body,
                email_context,
            )

            if status_code == 200:
                emails_sent += 1
            else:
                emails_failed += 1
                failures.append(
                    {
                        "email": user.email,
                        "error": response.get("Message", "Unknown error"),
                    }
                )
        except Exception as e:
            emails_failed += 1
            failures.append({"email": user.email, "error": str(e)})

    return {
        "message": f"Bulk email send completed for status: {request.status.value}",
        "total_recipients": len(users),
        "emails_sent": emails_sent,
        "emails_failed": emails_failed,
        "failures": failures if failures else None,
    }
