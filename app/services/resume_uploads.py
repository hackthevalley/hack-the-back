import logging
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO, Protocol
from uuid import uuid4

from pypdf import PdfReader
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session

from app.config import FileUploadConfig
from app.core.errors import ServiceError
from app.models.constants import (
    ALLOWED_FILE_EXTENSIONS,
    ALLOWED_FILE_TYPES_MESSAGE,
    DEFAULT_FILE_EXTENSION,
    MIN_PDF_PAGES,
    PDF_EMBEDDED_FILES_ERROR,
    PDF_ENCRYPTED_ERROR,
    PDF_JAVASCRIPT_ERROR,
    PDF_NO_PAGES_ERROR,
)
from app.models.user import AccountUser
from app.services.applications import create_application, is_valid_submission_time

logger = logging.getLogger(__name__)


class UploadedFile(Protocol):
    filename: str | None
    file: BinaryIO


def validate_pdf(filepath: str, filename: str) -> tuple[bool, str]:
    if Path(filename).suffix.lower() not in ALLOWED_FILE_EXTENSIONS:
        return False, ALLOWED_FILE_TYPES_MESSAGE
    try:
        reader = PdfReader(filepath)
        if reader.is_encrypted:
            return False, PDF_ENCRYPTED_ERROR
        if len(reader.pages) < MIN_PDF_PAGES:
            return False, PDF_NO_PAGES_ERROR

        def contains(forbidden_keys: set[str], value) -> bool:
            if isinstance(value, dict):
                return any(
                    key in forbidden_keys
                    or (
                        isinstance(child, (dict, list))
                        and contains(forbidden_keys, child)
                    )
                    for key, child in value.items()
                )
            if isinstance(value, list):
                return any(
                    isinstance(child, (dict, list)) and contains(forbidden_keys, child)
                    for child in value
                )
            return False

        root = reader.trailer.get("/Root")
        if contains({"/JavaScript", "/JS", "/AA", "/OpenAction"}, root):
            return False, PDF_JAVASCRIPT_ERROR
        if contains({"/EmbeddedFile", "/EmbeddedFiles", "/AF"}, root):
            return False, PDF_EMBEDDED_FILES_ERROR
    except Exception:
        logger.exception("PDF validation failed for uploaded file")
        return False, "Invalid PDF file"
    return True, ""


def upload_resume(
    session: Session, current_user: AccountUser, file: UploadedFile
) -> str:
    if not is_valid_submission_time(session, current_user):
        raise ServiceError(status_code=403, detail="Submission is closed")
    if not file.filename:
        raise ServiceError(status_code=400, detail="Filename is required")
    if Path(file.filename).suffix.lower() not in ALLOWED_FILE_EXTENSIONS:
        raise ServiceError(status_code=400, detail=ALLOWED_FILE_TYPES_MESSAGE)

    upload_dir = Path(FileUploadConfig.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        delete=False, dir=upload_dir, suffix=DEFAULT_FILE_EXTENSION
    ) as temporary_file:
        temporary_path = temporary_file.name
    final_path: Path | None = None

    try:
        with open(temporary_path, "wb") as output:
            bytes_written = 0
            while chunk := file.file.read(FileUploadConfig.CHUNK_SIZE_BYTES):
                bytes_written += len(chunk)
                if bytes_written > FileUploadConfig.MAX_FILE_SIZE_BYTES:
                    raise ServiceError(
                        status_code=413,
                        detail="File too large",
                    )
                output.write(chunk)

        valid, error = validate_pdf(temporary_path, file.filename)
        if not valid:
            raise ServiceError(status_code=400, detail=error)

        if current_user.application is None:
            current_user.application = create_application(current_user, session)
        application = current_user.application
        old_resume = application.form_answer_files
        old_path = (
            Path(old_resume.file_path) if old_resume and old_resume.file_path else None
        )

        final_path = upload_dir / f"{uuid4()}{DEFAULT_FILE_EXTENSION}"
        shutil.move(temporary_path, final_path)
        answer_file = application.form_answer_files
        if not answer_file:
            final_path.unlink(missing_ok=True)
            raise ServiceError(status_code=400, detail="Missing resume model")

        answer_file.original_filename = file.filename
        answer_file.file_path = str(final_path)
        application.updated_at = datetime.now(timezone.utc)
        session.add(answer_file)
        session.add(application)
        session.commit()
        session.refresh(answer_file)
        if old_path and old_path != final_path:
            try:
                old_path.unlink(missing_ok=True)
            except OSError:
                logger.warning("Could not remove replaced resume %s", old_path)
        return answer_file.original_filename
    except ServiceError:
        Path(temporary_path).unlink(missing_ok=True)
        if final_path:
            final_path.unlink(missing_ok=True)
        raise
    except (OSError, SQLAlchemyError) as error:
        session.rollback()
        Path(temporary_path).unlink(missing_ok=True)
        if final_path:
            final_path.unlink(missing_ok=True)
        logger.exception("Failed to save resume for user %s", current_user.uid)
        raise ServiceError(status_code=500, detail="Failed to save resume") from error
