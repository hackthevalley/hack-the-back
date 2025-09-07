from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import or_
from sqlmodel import select

from app.core.db import SessionDep
from app.models.forms import Forms_AnswerFile, Forms_Application, StatusEnum
from app.models.user import Account_User, UserPublic

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
    session: SessionDep, ofs: int = 0, limit: int = 25, search: str = ""
):
    statement = select(Account_User).where(
        Account_User.is_active,
        Account_User.application != None,  # noqa: E711
    )
    if search:
        search_pattern = f"%{search}%"
        statement = statement.where(
            or_(
                Account_User.first_name.ilike(search_pattern),
                Account_User.last_name.ilike(search_pattern),
                Account_User.email.ilike(search_pattern),
            )
        )
    statement = statement.offset(ofs).limit(limit)
    users = session.exec(statement).all()
    response = []
    for user in users:
        user_app = user.application
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
            }
        )
    return {"application": response, "offset": ofs, "limit": limit}


@router.put("/updatestatus/{application_id}")
async def update_application_status(
    application_id: str, request: StatusEnum, session: SessionDep
):
    application_statement = select(Forms_Application).where(
        Forms_Application.application_id == application_id
    )
    application = session.exec(application_statement).first()

    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    application.hackathonapplicant.status = request.value

    application.updated_at = datetime.now(timezone.utc)

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
