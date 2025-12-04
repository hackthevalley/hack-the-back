import io
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from pypdf import PdfReader
from sqlalchemy.orm import selectinload
from sqlmodel import select

from app.config import FileUploadConfig
from app.core.db import SessionDep
from app.models.constants import QuestionLabel
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


def validate_pdf_file(filename: str, content: bytes) -> tuple[bool, str]:
    if not filename.lower().endswith(".pdf"):
        return False, "Only PDF files are allowed"

    if len(content) < 100:
        return False, "File is too small to be a valid PDF"

    if not content.startswith(b"%PDF-"):
        if content[:2048].find(b"%PDF-") == -1:
            return False, "Missing PDF header (%PDF-) — file is not a valid PDF"

    eof_matches = re.findall(rb"%%EOF", content)
    if not eof_matches:
        return False, "Missing PDF EOF marker"

    if content.rfind(b"%%EOF") < len(content) - 4096:
        return False, "EOF marker too far from end — corrupted or incremental PDF"

    try:
        reader = PdfReader(io.BytesIO(content))

        if reader.is_encrypted:
            return False, "Encrypted or password-protected PDFs are not supported"

        if len(reader.pages) == 0:
            return False, "PDF contains no pages"

    except Exception as e:
        return False, f"PDF parsing error: {str(e)[:120]}"

    def object_contains(forbidden_keys, obj):
        """Recursively scan PDF dictionaries for forbidden keys."""
        if isinstance(obj, dict):
            for key, value in obj.items():
                if key in forbidden_keys:
                    return True
                if isinstance(value, (dict, list)):
                    if object_contains(forbidden_keys, value):
                        return True
        elif isinstance(obj, list):
            for item in obj:
                if isinstance(item, (dict, list)):
                    if object_contains(forbidden_keys, item):
                        return True
        return False

    root = reader.trailer.get("/Root")

    JS_KEYS = {"/JavaScript", "/JS", "/AA", "/OpenAction"}
    if object_contains(JS_KEYS, root):
        return False, "PDF contains JavaScript actions, which are not allowed"

    EMBED_KEYS = {"/EmbeddedFile", "/EmbeddedFiles", "/AF"}
    if object_contains(EMBED_KEYS, root):
        return False, "PDF contains embedded files, which are not allowed"

    return True, ""


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

    if current_user.application is None:
        application = await createapplication(current_user, session)
    else:
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

    statement = (
        select(Forms_Application)
        .where(Forms_Application.uid == current_user.uid)
        .options(selectinload(Forms_Application.form_answers))
    )
    application = session.exec(statement).first()

    answer_map = {str(ans.question_id): ans for ans in application.form_answers}

    questions_statement = select(Forms_Question)
    questions = session.exec(questions_statement).all()
    question_map = {str(q.question_id): q for q in questions}

    bulk_updates = []
    for update in forms_batchupdate:
        form_answer = answer_map.get(update.question_id)
        if form_answer:
            question = question_map.get(update.question_id)
            if question:
                is_prefilled_field = QuestionLabel.is_prefilled_field(question.label)
                has_existing_value = form_answer.answer and form_answer.answer.strip()
                is_empty_update = not update.answer or not update.answer.strip()

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

    application.updated_at = datetime.now(timezone.utc)
    session.add(application)
    session.commit()

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

    if file.size is not None and file.size > FileUploadConfig.MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds {FileUploadConfig.MAX_FILE_SIZE_BYTES // (1024 * 1024)}MB limit",
        )

    contents = b""
    while True:
        chunk = await file.read(FileUploadConfig.CHUNK_SIZE_BYTES)
        if not chunk:
            break
        contents += chunk
        if len(contents) > FileUploadConfig.MAX_FILE_SIZE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File exceeds {FileUploadConfig.MAX_FILE_SIZE_BYTES // (1024 * 1024)}MB limit",
            )

    is_valid, error_message = validate_pdf_file(file.filename, contents)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=error_message
        )

    upload_dir = Path(FileUploadConfig.UPLOAD_DIR)
    try:
        upload_dir.mkdir(parents=True, exist_ok=True)
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
                old_path.unlink()
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Failed to delete old resume: {e}"
            )
    filename = f"{uuid4()}.pdf"
    filepath = str(upload_dir / filename)
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
    if not await isValidSubmissionTime(session, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Submission is currently closed",
        )

    questions_statement = select(Forms_Question)
    all_questions = session.exec(questions_statement).all()
    question_map = {str(q.question_id): q for q in all_questions}

    for answer in current_user.application.form_answers:
        selected_question = question_map.get(str(answer.question_id))
        if selected_question and selected_question.required:
            if (
                answer.answer is None
                or answer.answer.strip() == ""
                or answer.answer == "false"
            ):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Required field not answered: {selected_question.label}",
                )
    if current_user.application.form_answersfile.original_filename is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Resume is required"
        )

    hacker_applicant = current_user.application.hackathonapplicant

    if hacker_applicant.is_already_submitted():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Application already submitted"
        )

    if not hacker_applicant.can_submit_application():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User not in valid state to submit",
        )

    is_walk_in_submission = False
    current_status = hacker_applicant.status

    if current_status == StatusEnum.APPLYING:
        hacker_applicant.status = StatusEnum.APPLIED
    elif current_status == StatusEnum.WALK_IN:
        hacker_applicant.status = StatusEnum.WALK_IN_SUBMITTED
        is_walk_in_submission = True
    if not current_user.application.is_draft:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Application has already been submitted",
        )
    else:
        current_user.application.is_draft = False
        current_user.application.updated_at = datetime.now(timezone.utc)
    session.add(hacker_applicant)
    session.add(current_user.application)
    session.commit()
    session.refresh(hacker_applicant)
    session.refresh(current_user.application)

    if is_walk_in_submission:
        from app.utils import send_rsvp

        application_id = str(current_user.application.application_id)
        user_full_name = current_user.full_name
        await send_rsvp(current_user.email, user_full_name, application_id)
    else:
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
