import io
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import Integer, and_, func, or_
from sqlalchemy.orm import aliased
from sqlmodel import select

from app.core.db import SessionDep
from app.models.forms import (
    Forms_Answer,
    Forms_AnswerFile,
    Forms_Application,
    Forms_Question,
    StatusEnum,
)
from app.models.user import Account_User, UserPublic
from app.utils import createQRCode, generate_google_wallet_pass, sendEmail

router = APIRouter()


@router.get("/getusers", response_model=list[UserPublic])
def get_users(
    session: SessionDep,
    offset: int = 0,
    limit: Annotated[int, Query(le=100)] = 100,
) -> list[UserPublic]:
    users = session.exec(select(Account_User).offset(offset).limit(limit)).all()
    return users


# Need to improve with search query instead of with just offsets
@router.get("/getapplicants")
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


@router.get("/file/{application_id}")
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


@router.get("/getapplication")
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


@router.get("/getallapps")
async def get_all_apps(
    session: SessionDep,
    ofs: int = 0,
    limit: int = 25,
    search: str = "",
    age: str = "",
    gender: str = "",
    school: str = "",
    date_sort: str = "",
):
    # Get question IDs for age and gender
    age_question = session.exec(
        select(Forms_Question).where(Forms_Question.label == "Age")
    ).first()
    gender_question = session.exec(
        select(Forms_Question).where(Forms_Question.label == "Gender")
    ).first()
    school_question = session.exec(
        select(Forms_Question).where(Forms_Question.label == "School Name")
    ).first()

    statement = select(Account_User).where(
        Account_User.is_active,
        Account_User.application != None,  # noqa: E711
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

    # Join with Forms_Application first (only once)
    statement = statement.join(
        Forms_Application, Account_User.uid == Forms_Application.uid
    )

    # Apply age filter
    if age and age_question:
        # Use alias to avoid conflicts with gender join
        age_answer = aliased(Forms_Answer)

        statement = statement.join(
            age_answer,
            and_(
                age_answer.application_id == Forms_Application.application_id,
                age_answer.question_id == age_question.question_id,
            ),
        )

        MAX_AGE = 40
        # Handle age range filtering
        if age == f"{MAX_AGE}+":
            # UI only supports until 40 so this handles 40+
            statement = statement.where(
                and_(
                    age_answer.answer.isnot(None),
                    age_answer.answer != "",
                    age_answer.answer.cast(Integer) >= MAX_AGE,
                )
            )
        elif "-" in age:
            # Handle range. E.g. (18-20)
            min_age, max_age = age.split("-")
            statement = statement.where(
                and_(
                    age_answer.answer.isnot(None),
                    age_answer.answer != "",
                    age_answer.answer.cast(Integer) >= int(min_age),
                    age_answer.answer.cast(Integer) <= int(max_age),
                )
            )
        else:
            # Fallback to exact match for any other format
            statement = statement.where(age_answer.answer.ilike(f"%{age}%"))

    # Apply gender filter
    if gender and gender_question:
        # Use alias to avoid conflicts with age join
        gender_answer = aliased(Forms_Answer)

        statement = statement.join(
            gender_answer,
            and_(
                gender_answer.application_id == Forms_Application.application_id,
                gender_answer.question_id == gender_question.question_id,
            ),
        ).where(func.lower(gender_answer.answer) == gender.lower())

    # Apply school filter
    if school and school_question:
        # Use alias to avoid conflicts with other joins
        school_answer = aliased(Forms_Answer)

        statement = statement.join(
            school_answer,
            and_(
                school_answer.application_id == Forms_Application.application_id,
                school_answer.question_id == school_question.question_id,
            ),
        ).where(
            and_(
                school_answer.answer.isnot(None),
                school_answer.answer != "",
                func.lower(school_answer.answer) == school.lower(),
            )
        )

    # Apply date sorting
    if date_sort:
        if date_sort == "oldest":
            statement = statement.order_by(Forms_Application.updated_at.asc())
        elif date_sort == "latest":
            statement = statement.order_by(Forms_Application.updated_at.desc())
    statement = statement.offset(ofs).limit(limit)
    users = session.exec(statement).all()
    response = []
    for user in users:
        user_app = user.application
        user_age = None
        user_gender = None
        user_school = None
        if user_app and age_question:
            age_answer = session.exec(
                select(Forms_Answer).where(
                    and_(
                        Forms_Answer.application_id == user_app.application_id,
                        Forms_Answer.question_id == age_question.question_id,
                    )
                )
            ).first()
            user_age = age_answer.answer if age_answer else None

        if user_app and gender_question:
            gender_answer = session.exec(
                select(Forms_Answer).where(
                    and_(
                        Forms_Answer.application_id == user_app.application_id,
                        Forms_Answer.question_id == gender_question.question_id,
                    )
                )
            ).first()
            user_gender = gender_answer.answer if gender_answer else None

        if user_app and school_question:
            school_answer = session.exec(
                select(Forms_Answer).where(
                    and_(
                        Forms_Answer.application_id == user_app.application_id,
                        Forms_Answer.question_id == school_question.question_id,
                    )
                )
            ).first()
            user_school = school_answer.answer if school_answer else None

        response.append(
            {
                "first_name": user.first_name,
                "last_name": user.last_name,
                "email": user.email,
                "status": user_app.hackathonapplicant.status if user_app else None,
                "app_id": user_app.hackathonapplicant.application_id
                if user_app
                else None,
                "created_at": user_app.created_at if user_app else None,
                "updated_at": user_app.updated_at if user_app else None,
                "age": user_age,
                "gender": user_gender,
                "school": user_school,
            }
        )
    return {"application": response, "offset": ofs, "limit": limit}


@router.put("/updatestatus/{application_id}")
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
                "apple_url": f"apple_wallet/{application_id}",
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
