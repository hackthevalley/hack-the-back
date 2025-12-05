import asyncio
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated
from uuid import uuid4

import aiofiles
from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from pypdf import PdfReader
from sqlalchemy.orm import selectinload
from sqlmodel import select

from app.config import FileUploadConfig
from app.core.db import SessionDep
from app.models.constants import (
    EmailMessage,
    EmailSubject,
    EmailTemplate,
    QuestionLabel,
)
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


def _validate_pdf(filepath: str, filename: str) -> tuple[bool, str]:
    """
    Validate PDF file directly from disk without loading into memory.

    This function runs in a thread pool to avoid blocking the async event loop.
    PyPDF's PdfReader efficiently reads from the file path without loading
    the entire file into RAM at once.

    Args:
        filepath: Path to the PDF file on disk
        filename: Original filename for extension validation

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not filename.lower().endswith(".pdf"):
        return False, "Only PDF files are allowed"

    try:
        reader = PdfReader(filepath)
        if reader.is_encrypted:
            return False, "Encrypted or password-protected PDFs are not supported"

        if len(reader.pages) == 0:
            return False, "PDF contains no pages"

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

    except Exception as e:
        return False, f"Invalid PDF: {str(e)[:120]}"

    return True, ""


@router.get("/questions")
def getquestions(session: SessionDep) -> list[Forms_Question]:
    """
    Get all form questions.

    Results are cached for 10 minutes since questions rarely change.
    """
    from datetime import timedelta

    from app.cache import cache

    def fetch_questions():
        statement = select(Forms_Question).order_by(Forms_Question.question_order)
        return list(session.exec(statement).all())

    return cache.get_or_set(
        key="form_questions", factory_func=fetch_questions, ttl=timedelta(minutes=10)
    )


@router.get("/application", response_model=ApplicationResponse)
async def getapplication(
    current_user: Annotated[Account_User, Depends(get_current_user)],
    session: SessionDep,
):
    if not await isValidSubmissionTime(session, current_user):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Submitting outside submission time",
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

    try:
        if bulk_updates:
            session.bulk_update_mappings(Forms_Answer, bulk_updates)

        application.updated_at = datetime.now(timezone.utc)
        session.add(application)

        session.commit()
        session.refresh(application)
    except Exception as e:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save answers: {str(e)}",
        )

    return {"message": "Answers saved successfully", "updated_count": len(bulk_updates)}


@router.post("/resume")
async def uploadresume(
    file: UploadFile,
    current_user: Annotated[Account_User, Depends(get_current_user)],
    session: SessionDep,
):
    if not await isValidSubmissionTime(session, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Submission is closed"
        )

    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Only PDF files are allowed"
        )

    upload_dir = Path(FileUploadConfig.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile(
        delete=False, dir=upload_dir, suffix=".pdf"
    ) as tmp:
        temp_path = tmp.name
    async with aiofiles.open(temp_path, "wb") as out:
        bytes_written = 0

        while chunk := await file.read(FileUploadConfig.CHUNK_SIZE_BYTES):
            bytes_written += len(chunk)
            if bytes_written > FileUploadConfig.MAX_FILE_SIZE_BYTES:
                await out.close()
                os.unlink(temp_path)
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail="File too large",
                )
            await out.write(chunk)

    is_valid, error_msg = await asyncio.to_thread(
        _validate_pdf, temp_path, file.filename
    )
    if not is_valid:
        os.unlink(temp_path)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)

    if current_user.application is None:
        current_user.application = await createapplication(current_user, session)

    old = current_user.application.form_answersfile
    if old and old.file_path:
        try:
            Path(old.file_path).unlink(missing_ok=True)
        except Exception:
            pass

    final_name = f"{uuid4()}.pdf"
    final_path = upload_dir / final_name
    shutil.move(temp_path, final_path)

    answer_file = current_user.application.form_answersfile
    if not answer_file:
        try:
            final_path.unlink(missing_ok=True)
        except Exception:
            pass
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Missing resume model"
        )

    try:
        answer_file.original_filename = file.filename
        answer_file.file_path = str(final_path)
        current_user.application.updated_at = datetime.now(timezone.utc)

        session.add(answer_file)
        session.add(current_user.application)
        session.commit()
        session.refresh(answer_file)
    except Exception as e:
        session.rollback()
        try:
            final_path.unlink(missing_ok=True)
        except Exception:
            pass
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save resume: {str(e)}",
        )

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

    try:
        session.add(hacker_applicant)
        session.add(current_user.application)
        session.commit()
        session.refresh(hacker_applicant)
        session.refresh(current_user.application)
    except Exception as e:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to submit application: {str(e)}",
        )

    if is_walk_in_submission:
        from app.utils import send_rsvp

        application_id = str(current_user.application.application_id)
        user_full_name = current_user.full_name
        await send_rsvp(current_user.email, user_full_name, application_id)
    else:
        await sendEmail(
            EmailTemplate.CONFIRMATION,
            current_user.email,
            EmailSubject.CONFIRMATION,
            EmailMessage.CONFIRMATION,
            {},
        )

    return "Success"


@router.get("/submission-time")
async def submissiontime(session: SessionDep):
    return await isValidSubmissionTime(session)


@router.get("/registration-timerange", response_model=Forms_Form)
def get_reg_time_range(session: SessionDep) -> Forms_Form:
    """
    Get registration time range.

    Results are cached for 5 minutes since this rarely changes.
    """
    from datetime import timedelta

    from app.cache import cache

    def fetch_time_range():
        return session.exec(select(Forms_Form)).first()

    return cache.get_or_set(
        key="registration_timerange",
        factory_func=fetch_time_range,
        ttl=timedelta(minutes=5),
    )
