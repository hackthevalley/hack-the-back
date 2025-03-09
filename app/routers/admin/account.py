from io import BytesIO
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlmodel import select

from app.core.db import SessionDep
from app.models.forms import Forms_AnswerFile
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
    if resume is None:
        raise HTTPException(status_code=404, detail="Resume not found")
    file_stream = BytesIO(resume.file)

    return StreamingResponse(
        file_stream,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename={resume.original_filename}"
        },
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
        "form_answersfile": application.form_answersfile.original_filename,
    }
