from datetime import datetime, timezone
from importlib import import_module
from pathlib import Path
import zipfile

from sqlmodel import Session, SQLModel, create_engine

from app.models.constants import QuestionLabel, UserRole
from app.models.forms import (
    FormAnswer,
    FormAnswerFile,
    FormApplication,
    FormQuestion,
    HackathonApplicant,
    StatusEnum,
)
from app.models.user import AccountUser
from app.services.admin_applications import create_resume_export, sanitize_filename

bulk_email = import_module("app.services.bulk_email")


def test_filename_sanitization():
    assert sanitize_filename("../../bad<script>.pdf") == "badscript.pdf"
    assert sanitize_filename("...") == "file.pdf"
    assert len(sanitize_filename("a" * 300 + ".pdf")) == 255
    assert len(sanitize_filename("a" * 300)) == 255


def test_batch_email_success_failure_and_exception(monkeypatch):
    responses = iter([(200, {"ok": True}), (500, {"ok": False})])

    def fake_send(*_args, **_kwargs):
        return next(responses)

    monkeypatch.setattr(bulk_email, "send_email", fake_send)
    bulk_email.send_batch_email(
        [{"email": "ok@example.com"}, {"email": "bad@example.com"}],
        "template",
        "subject",
        "body",
        None,
    )

    def exploding(*_args, **_kwargs):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(bulk_email, "send_email", exploding)
    bulk_email.send_batch_email(
        [{}], "template", "subject", "body", {"shared": True}
    )


def test_resume_export_filters_and_sorts(tmp_path):
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    now = datetime.now(timezone.utc)
    level_question = FormQuestion(
        question_order=0,
        label=QuestionLabel.CURRENT_LEVEL_OF_STUDY.value,
        required=True,
    )
    resume_question = FormQuestion(
        question_order=1,
        label=QuestionLabel.RESUME.value,
        required=True,
    )

    with Session(engine) as session:
        session.add_all([level_question, resume_question])
        session.flush()
        for index, (first_name, last_name, status, study_level) in enumerate(
            [
                ("Zoe", "Able", StatusEnum.APPLIED, "Freshman - Undergraduate"),
                ("Amy", "Baker", StatusEnum.APPLIED, "Freshman - Undergraduate"),
                ("Moe", "Cross", StatusEnum.REJECTED, "PhD"),
            ]
        ):
            user = AccountUser(
                first_name=first_name,
                last_name=last_name,
                email=f"person{index}@example.com",
                password="unused",
                role=UserRole.HACKER,
                is_active=True,
            )
            session.add(user)
            session.flush()
            application = FormApplication(
                uid=user.uid,
                is_draft=False,
                created_at=now,
                updated_at=now,
            )
            session.add(application)
            session.flush()
            resume_path = tmp_path / f"resume-{index}.pdf"
            resume_path.write_bytes(f"resume {index}".encode())
            session.add_all(
                [
                    HackathonApplicant(
                        application_id=application.application_id,
                        status=status,
                    ),
                    FormAnswer(
                        application_id=application.application_id,
                        question_id=level_question.question_id,
                        answer=study_level,
                    ),
                    FormAnswerFile(
                        application_id=application.application_id,
                        question_id=resume_question.question_id,
                        original_filename=f"original-{index}.pdf",
                        file_path=str(resume_path),
                    ),
                ]
            )
        session.commit()

        export_path, exported = create_resume_export(
            session,
            level_of_study="Freshman - Undergraduate",
            application_status=StatusEnum.APPLIED,
        )

    try:
        assert exported == 2
        with zipfile.ZipFile(export_path) as archive:
            resume_names = [
                name for name in archive.namelist() if name.startswith("resumes/")
            ]
            assert "_Able_Zoe_" in resume_names[0]
            assert "_Baker_Amy_" in resume_names[1]
            manifest = archive.read("manifest.csv").decode()
            assert "person0@example.com" in manifest
            assert "person1@example.com" in manifest
            assert "person2@example.com" not in manifest
    finally:
        Path(export_path).unlink(missing_ok=True)
        engine.dispose()
