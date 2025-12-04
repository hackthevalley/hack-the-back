import io
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from pypdf import PdfReader
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


def validate_pdf_file(filename: str, content: bytes) -> tuple[bool, str]:
    if not filename.lower().endswith(".pdf"):
        return False, "Only PDF files are allowed"

    if len(content) < 5:
        return False, "File is too small to be a valid PDF"

    pdf_signature = content[:5]
    if pdf_signature != b"%PDF-":
        return False, "File content does not match PDF format (invalid magic bytes)"

    try:
        pdf_file = io.BytesIO(content)

        reader = PdfReader(pdf_file)

        if len(reader.pages) < 1:
            return False, "PDF file must contain at least one page"

        _ = reader.pages[0]

        if reader.is_encrypted:
            return False, "Encrypted or password-protected PDFs are not supported"

        return True, ""

    except Exception as e:
        error_msg = str(e)

        if "EOF" in error_msg or "marker" in error_msg or "xref" in error_msg:
            return False, "PDF file is corrupted or incomplete"
        elif "encrypt" in error_msg.lower() or "password" in error_msg.lower():
            return False, "Encrypted or password-protected PDFs are not supported"
        elif "invalid" in error_msg.lower():
            return False, "Invalid PDF structure detected"
        else:
            return False, f"Invalid PDF file: {error_msg[:100]}"


@router.get("/questions")
async def getquestions(session: SessionDep) -> list[Forms_Question]:
    statement = select(Forms_Question)
    return session.exec(statement)


@router.get("/application", response_model=ApplicationResponse)
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


@router.put("/answers")
async def saveAnswers(
    forms_batchupdate: list[Forms_AnswerUpdate],
    current_user: Annotated[Account_User, Depends(get_current_user)],
    session: SessionDep,
):
    if not await isValidSubmissionTime(session, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Submission is currently closed",
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

    # Fetch questions to check for pre-filled fields
    questions_statement = select(Forms_Question)
    questions = session.exec(questions_statement).all()
    question_map = {str(q.question_id): q for q in questions}

    bulk_updates = []
    for update in forms_batchupdate:
        form_answer = answer_map.get(update.question_id)
        if form_answer:
            # Prevent overwriting pre-filled fields (First Name, Last Name, Email) with empty values
            question = question_map.get(update.question_id)
            if question:
                label_lower = question.label.lower().strip()
                is_prefilled_field = label_lower in ["first name", "last name", "email"]
                has_existing_value = form_answer.answer and form_answer.answer.strip()
                is_empty_update = not update.answer or not update.answer.strip()

                # Skip update if trying to overwrite pre-filled field with empty value
                if is_prefilled_field and has_existing_value and is_empty_update:
                    continue

            bulk_updates.append({"id": form_answer.id, "answer": update.answer})
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid question_id: {update.question_id}",
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


@router.post("/resume")
async def uploadresume(
    file: UploadFile,
    current_user: Annotated[Account_User, Depends(get_current_user)],
    session: SessionDep,
):
    if not await isValidSubmissionTime(session, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Submission is currently closed",
        )

    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Filename is required"
        )

    if file.content_type and file.content_type not in [
        "application/pdf",
        "application/x-pdf",
    ]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid content type: {file.content_type}. Only PDF files are allowed",
        )

    if file.size is not None and file.size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File exceeds 5MB limit",
        )

    contents = b""
    chunk_size = 1024 * 1024
    while True:
        chunk = await file.read(chunk_size)
        if not chunk:
            break
        contents += chunk
        if len(contents) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="File exceeds 5MB limit",
            )

    is_valid, error_message = validate_pdf_file(file.filename, contents)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=error_message
        )

    try:
        os.makedirs(UPLOAD_DIR, exist_ok=True)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to prepare upload directory: {e}"
        )

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


@router.post("/submission", status_code=status.HTTP_201_CREATED)
async def submit(
    current_user: Annotated[Account_User, Depends(get_current_user)],
    session: SessionDep,
):
    # Check if all mandatory ones are ok + is applying + isdraft + is within the application time
    if not await isValidSubmissionTime(session, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Submission is currently closed",
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
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Required field not answered: {selected_question.label}",
                )
    if current_user.application.form_answersfile.original_filename is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Resume is required"
        )

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
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Application already submitted"
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User not in valid state to submit",
        )
    if not current_user.application.is_draft:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Application has already been submitted",
        )
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
                "apple_url": f"apple-wallet/{application_id}",
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


@router.get("/submission-time")
async def submissiontime(session: SessionDep):
    return await isValidSubmissionTime(session)


@router.get("/registration-timerange", response_model=Forms_Form)
async def get_reg_time_range(session: SessionDep) -> Forms_Form:
    time_range = session.exec(select(Forms_Form)).first()
    return time_range
