import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.orm import selectinload
from sqlmodel import select

from app.core.db import SessionDep
from app.models.forms import (
    ApplicationResponse,
    Forms_Answer,
    Forms_AnswerUpdate,
    Forms_Application,
    Forms_Form,
    Forms_Question,
    StatusEnum,
)
from app.models.user import Account_User
from app.utils import (
    createapplication,
    get_current_user,
    isValidSubmissionTime,
    sendEmail,
)

router = APIRouter()

UPLOAD_DIR = os.getenv("UPLOAD_DIR")
MAX_FILE_SIZE = 5 * 1024 * 1024


@router.get("/getquestions")
async def getquestions(session: SessionDep) -> list[Forms_Question]:
    statement = select(Forms_Question)
    return session.exec(statement)


@router.get("/getapplication", response_model=ApplicationResponse)
async def getapplication(
    current_user: Annotated[Account_User, Depends(get_current_user)],
    session: SessionDep,
):
    if not await isValidSubmissionTime(session, current_user):
        raise HTTPException(
            status_code=404, detail="Submitting outside submission time"
        )

    # Optimize: Use eager loading to fetch everything in one query
    if current_user.application is None:
        application = await createapplication(current_user, session)
    else:
        # Fetch application with all related data in a single query
        statement = (
            select(Forms_Application)
            .where(Forms_Application.uid == current_user.uid)
            .options(
                selectinload(Forms_Application.form_answers),
                selectinload(Forms_Application.form_answersfile),
                selectinload(Forms_Application.hackathonapplicant),
            )
        )
        application = session.exec(statement).first()

    return {
        "application": application,
        "form_answers": application.form_answers,
        "form_answersfile": application.form_answersfile.original_filename
        if application.form_answersfile
        else None,
    }


@router.post("/saveAnswers")
async def saveAnswers(
    forms_batchupdate: list[Forms_AnswerUpdate],
    current_user: Annotated[Account_User, Depends(get_current_user)],
    session: SessionDep,
):
    if not await isValidSubmissionTime(session, current_user):
        raise HTTPException(
            status_code=404, detail="Submitting outside submission time"
        )

    if current_user.application is None:
        current_user.application = await createapplication(current_user, session)

    # Optimize: Fetch all answers in one query with eager loading
    statement = (
        select(Forms_Application)
        .where(Forms_Application.uid == current_user.uid)
        .options(selectinload(Forms_Application.form_answers))
    )
    application = session.exec(statement).first()

    answer_map = {str(ans.question_id): ans for ans in application.form_answers}

    bulk_updates = []
    for update in forms_batchupdate:
        form_answer = answer_map.get(update.question_id)
        if form_answer:
            bulk_updates.append({"id": form_answer.id, "answer": update.answer})
        else:
            raise HTTPException(
                status_code=404,
                detail=f"Form Application not found for question_id: {update.question_id}",
            )

    if bulk_updates:
        session.bulk_update_mappings(Forms_Answer, bulk_updates)
        session.commit()

    # Update application timestamp
    application.updated_at = datetime.now(timezone.utc)
    session.add(application)
    session.commit()

    # Refresh only the application object instead of individual answers
    session.refresh(application)

    return {"message": "Answers saved successfully", "updated_count": len(bulk_updates)}


@router.post("/uploadresume")
async def uploadresume(
    file: UploadFile,
    current_user: Annotated[Account_User, Depends(get_current_user)],
    session: SessionDep,
):
    if not await isValidSubmissionTime(session, current_user):
        raise HTTPException(
            status_code=404, detail="Submitting outside submission time"
        )
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=404, detail="File not pdf")

    # Check file size before reading
    # Method 1: Try to get size from headers if available
    if file.size is not None and file.size > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File exceeds 5MB limit")

    # Method 2: Read file in chunks to check size without loading entire file into memory
    contents = b""
    chunk_size = 1024 * 1024  # 1MB chunks
    while True:
        chunk = await file.read(chunk_size)
        if not chunk:
            break
        contents += chunk
        if len(contents) > MAX_FILE_SIZE:
            raise HTTPException(status_code=413, detail="File exceeds 5MB limit")

    # Reset file position to beginning after reading
    await file.seek(0)

    # Ensure upload directory exists and is a valid path
    try:
        os.makedirs(UPLOAD_DIR, exist_ok=True)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to prepare upload directory: {e}"
        )

    # Ensure application exists (parity with saveAnswers)
    if current_user.application is None:
        current_user.application = await createapplication(current_user, session)
    answer_file = current_user.application.form_answersfile
    if answer_file and answer_file.file_path:
        try:
            old_path = Path(answer_file.file_path)
            if old_path.exists():
                old_path.unlink()  # deletes file
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Failed to delete old resume: {e}"
            )
    filename = f"{uuid4()}.pdf"
    filepath = os.path.join(UPLOAD_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(contents)
    answer_file = current_user.application.form_answersfile
    if answer_file is None:
        # We cannot create a new Forms_AnswerFile without a question_id here.
        # Return a clear error instead of throwing an AttributeError.
        raise HTTPException(
            status_code=400, detail="Resume record not initialized for application"
        )
    answer_file.original_filename = file.filename
    answer_file.file_path = filepath
    current_user.application.updated_at = datetime.now(timezone.utc)
    session.add(answer_file)
    session.add(current_user.application)
    session.commit()
    session.refresh(answer_file)
    return answer_file.original_filename


@router.post("/submit")
async def submit(
    current_user: Annotated[Account_User, Depends(get_current_user)],
    session: SessionDep,
):
    # Check if all mandatory ones are ok + is applying + isdraft + is within the application time
    if not await isValidSubmissionTime(session, current_user):
        raise HTTPException(
            status_code=404, detail="Submitting outside submission time"
        )
    for answer in current_user.application.form_answers:
        if answer.answer is not None and (
            answer.answer.strip() == "" or answer.answer == "false"
        ):
            statement = select(Forms_Question).where(
                Forms_Question.question_id == answer.question_id
            )
            selected_question = session.exec(statement).first()
            if selected_question and selected_question.required:
                raise HTTPException(
                    status_code=404, detail=f"{selected_question.label} not answered"
                )
    if current_user.application.form_answersfile.original_filename is None:
        raise HTTPException(status_code=404, detail="Resume not uploaded")

    current_status = current_user.application.hackathonapplicant.status

    # Check if user is in a valid state to submit
    is_walk_in_submission = False

    if current_status == StatusEnum.APPLYING:
        current_user.application.hackathonapplicant.status = StatusEnum.APPLIED
    elif current_status == StatusEnum.WALK_IN:
        current_user.application.hackathonapplicant.status = (
            StatusEnum.WALK_IN_SUBMITTED
        )
        is_walk_in_submission = True
    elif current_status in [StatusEnum.APPLIED, StatusEnum.WALK_IN_SUBMITTED]:
        raise HTTPException(status_code=400, detail="Application already submitted")
    else:
        raise HTTPException(status_code=400, detail="User not in valid state to submit")
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

    # Send appropriate email based on submission type
    if is_walk_in_submission:
        # Walk-in submission - send RSVP email with QR code
        import io

        from app.utils import createQRCode, generate_google_wallet_pass

        application_id = str(current_user.application.application_id)
        img = await createQRCode(application_id)
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="PNG")
        img_bytes.seek(0)

        google_link = generate_google_wallet_pass(
            f"{current_user.first_name} {current_user.last_name}", application_id
        )

        await sendEmail(
            "templates/rsvp.html",
            current_user.email,
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
    else:
        # Regular submission - send confirmation email
        await sendEmail(
            "templates/confirmation.html",
            current_user.email,
            "Application Submitted",
            "You have successfully submitted your application",
            {},
        )

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
