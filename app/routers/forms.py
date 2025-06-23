from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlmodel import select

from app.core.db import SessionDep
from app.models.forms import (
    ApplicationResponse,
    Forms_AnswerUpdate,
    Forms_Form,
    Forms_Question,
    StatusEnum,
)
from app.models.user import Account_User
from app.utils import createapplication, get_current_user, isValidSubmissionTime

router = APIRouter()


@router.get("/getquestions")
async def getquestions(session: SessionDep) -> list[Forms_Question]:
    statement = select(Forms_Question)
    return session.exec(statement)


@router.get("/getapplication", response_model=ApplicationResponse)
async def getapplication(
    current_user: Annotated[Account_User, Depends(get_current_user)],
    session: SessionDep,
):
    if not await isValidSubmissionTime(session):
        raise HTTPException(
            status_code=404, detail="Submitting outside submission time"
        )
    application = current_user.application
    if application is None:
        application = await createapplication(current_user, session)
    return {
        "application": application,
        "form_answers": application.form_answers,
        "form_answersfile": application.form_answersfile.original_filename,
    }


@router.post("/saveAnswers")
async def saveAnswers(
    forms_batchupdate: list[Forms_AnswerUpdate],
    current_user: Annotated[Account_User, Depends(get_current_user)],
    session: SessionDep,
):
    if not await isValidSubmissionTime(session):
        raise HTTPException(
            status_code=404, detail="Submitting outside submission time"
        )

    if current_user.application is None:
        current_user.application = await createapplication(current_user, session)

    answer_map = {
        str(ans.question_id): ans for ans in current_user.application.form_answers
    }

    for update in forms_batchupdate:
        form_answer = answer_map.get(update.question_id)
        if form_answer:
            form_answer.answer = update.answer
            session.add(form_answer)
        else:
            raise HTTPException(
                status_code=404,
                detail=f"Form Application not found for question_id: {update.question_id}",
            )

    current_user.application.updated_at = datetime.now(timezone.utc)
    session.add(current_user.application)
    session.commit()
    session.refresh(current_user.application)


@router.post("/uploadresume")
async def uploadresume(
    file: UploadFile,
    current_user: Annotated[Account_User, Depends(get_current_user)],
    session: SessionDep,
):
    if not await isValidSubmissionTime(session):
        raise HTTPException(
            status_code=404, detail="Submitting outside submission time"
        )
    if file.filename.endswith(".pdf"):
        file_data = await file.read()
        current_user.application.form_answersfile.original_filename = file.filename
        current_user.application.form_answersfile.file = file_data
        current_user.application.updated_at = datetime.now(timezone.utc)
        session.add(current_user.application.form_answersfile)
        session.add(current_user.application)
        session.commit()
        session.refresh(current_user.application.form_answersfile)
        session.refresh(current_user.application)
        return current_user.application.form_answersfile.original_filename
    else:
        raise HTTPException(status_code=404, detail="File not pdf")


@router.post("/submit")
async def submit(
    current_user: Annotated[Account_User, Depends(get_current_user)],
    session: SessionDep,
):
    # Check if all mandatory ones are ok + is applying + isdraft + is within the application time
    if not await isValidSubmissionTime(session):
        raise HTTPException(
            status_code=404, detail="Submitting outside submission time"
        )
    for answer in current_user.application.form_answers:
        if answer.answer is None or answer.answer is False:
            statement = select(Forms_Question).where(
                Forms_Question.question_id == answer.question_id
            )
            selected_question = session.exec(statement).first()
            if selected_question.required:
                raise HTTPException(
                    status_code=404, detail=f"{selected_question.label} not answered"
                )
    if current_user.application.form_answersfile.original_filename is None:
        raise HTTPException(status_code=404, detail="Resume not uploaded")
    if not current_user.application.hackathonapplicant.status == StatusEnum.APPLYING:
        raise HTTPException(status_code=404, detail="User not applying")
    else:
        current_user.application.hackathonapplicant.status = StatusEnum.APPLIED
    if not current_user.application.is_draft:
        raise HTTPException(status_code=404, detail="Application not draft")
    else:
        current_user.application.is_draft = False
        current_user.application.updated_at = datetime.now(timezone.utc)
    session.add(current_user.application.hackathonapplicant)
    session.add(current_user.application)
    session.commit()
    session.refresh(current_user.application.hackathonapplicant)
    session.refresh(current_user.application)
    return "Success"


@router.get("/submissiontime")
async def submissiontime(session: SessionDep):
    return await isValidSubmissionTime(session)


@router.get("/getregtimerange", response_model=Forms_Form)
async def get_reg_time_range(session: SessionDep) -> Forms_Form:
    """
    Retrieve the current hackathon registration time range.

    Args:
        session (SessionDep): Database session dependency.

    Returns:
        Forms_Form: The current registration time range for Hack the Valley Hackathon.
    """
    time_range = session.exec(select(Forms_Form)).first()
    return time_range
