import os
from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from sqlmodel import select

from app.core.db import SessionDep
from app.models.forms import Forms_AnswerFile, Forms_Application, StatusEnum
from app.models.requests import UIDRequest
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
    statement = select(Forms_AnswerFile).where(
        Forms_AnswerFile.application_id == application_id
    )
    resume = session.exec(statement).first()

    if resume is None or not resume.file_path:
        raise HTTPException(status_code=404, detail="Resume not found")

    if not os.path.exists(resume.file_path):
        raise HTTPException(status_code=404, detail="File not found on disk")

    return FileResponse(
        path=resume.file_path,
        media_type="application/pdf",
        filename=resume.original_filename,
    )


@router.get("/getapplication")
async def getapplication(uid: UIDRequest, session: SessionDep):
    statement = select(Account_User).where(Account_User.uid == uid.uid)
    selected_user = session.exec(statement).first()
    if selected_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    application = selected_user.application
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
async def get_all_apps(session: SessionDep, ofs: int = 0, limit: int = 25):
    statement = (
        select(Account_User)
        .where(Account_User.is_active, Account_User.application is not None)
        .offset(ofs)
        .limit(limit)
    )

    users = session.exec(statement).all()

    if users is None:
        raise HTTPException(status_code=404, detail="Statement error...")

    response = []
    for user in users:
        user_app = user.application
        response.append(
            {
                "first_name": user.first_name,
                "last_name": user.last_name,
                "email": user.email,
                "status": user_app.hackathonapplicant.status,
                "app_id": user_app.hackathonapplicant.application_id,
                "created_at": user.application.created_at if user_app else None,
                "updated_at": user.application.updated_at if user_app else None,
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
