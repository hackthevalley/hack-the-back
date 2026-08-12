import logging
from collections.abc import Callable
from datetime import datetime, timezone

from sqlmodel import Session, select
from sqlalchemy.exc import SQLAlchemyError

from app.core.errors import ServiceError
from app.core.orm import eager_load
from app.models.constants import (
    EmailMessage,
    EmailSubject,
    EmailTemplate,
    QuestionLabel,
)
from app.models.forms import (
    FormAnswer,
    FormApplication,
    HackathonApplicant,
    FormQuestion,
    StatusEnum,
)
from app.models.user import AccountUser
from app.schemas.forms import FormAnswerUpdate
from app.services.applications import create_application, is_valid_submission_time
from app.services.email import send_email_safely, send_rsvp_safely
from app.validators import validate_profile_url

logger = logging.getLogger(__name__)


def get_or_create_application(session: Session, user: AccountUser) -> dict:
    if user.application is None:
        if not is_valid_submission_time(session, user):
            raise ServiceError(
                status_code=404, detail="Submitting outside submission time"
            )
        application = create_application(user, session)
    else:
        application = session.exec(
            select(FormApplication)
            .where(FormApplication.uid == user.uid)
            .options(
                eager_load(FormApplication.form_answers),
                eager_load(FormApplication.form_answer_files),
                eager_load(FormApplication.hacker_applicant),
            )
        ).first()
    if application is None:
        raise ServiceError(status_code=404, detail="Application not found")
    return {
        "application": application,
        "form_answers": application.form_answers,
        "form_answer_files": application.form_answer_files.original_filename
        if application.form_answer_files
        else None,
    }


def save_answers(
    session: Session,
    user: AccountUser,
    updates: list[FormAnswerUpdate],
) -> dict:
    if not is_valid_submission_time(session, user):
        raise ServiceError(status_code=403, detail="Submission is currently closed")
    if user.application is None:
        user.application = create_application(user, session)

    application = session.exec(
        select(FormApplication)
        .where(FormApplication.uid == user.uid)
        .options(eager_load(FormApplication.form_answers))
    ).first()
    if application is None:
        raise ServiceError(status_code=404, detail="Application not found")

    answers = {str(answer.question_id): answer for answer in application.form_answers}
    questions = {
        str(question.question_id): question
        for question in session.exec(select(FormQuestion)).all()
    }
    bulk_updates: list[dict] = []
    for update in updates:
        answer = answers.get(update.question_id)
        if answer is None:
            raise ServiceError(
                status_code=400, detail=f"Invalid question_id: {update.question_id}"
            )
        question = questions.get(update.question_id)
        if question:
            if QuestionLabel.is_prefilled_field(question.label):
                continue
            try:
                validate_profile_url(question.label, update.answer)
            except ValueError as error:
                raise ServiceError(status_code=400, detail=str(error)) from error
        bulk_updates.append({"id": answer.id, "answer": update.answer})

    try:
        if bulk_updates:
            session.bulk_update_mappings(FormAnswer, bulk_updates)
        application.updated_at = datetime.now(timezone.utc)
        session.add(application)
        session.commit()
        session.refresh(application)
    except SQLAlchemyError as error:
        session.rollback()
        logger.exception(
            "Failed to save answers for application %s", application.application_id
        )
        raise ServiceError(status_code=500, detail="Failed to save answers") from error
    return {"message": "Answers saved successfully", "updated_count": len(bulk_updates)}


def submit_application(
    session: Session,
    user: AccountUser,
    enqueue: Callable[..., None] | None = None,
) -> str:
    if not is_valid_submission_time(session, user):
        raise ServiceError(status_code=403, detail="Submission is currently closed")
    application = user.application
    if application is None:
        raise ServiceError(status_code=404, detail="Application not found")

    all_questions = session.exec(select(FormQuestion)).all()
    questions = {str(question.question_id): question for question in all_questions}
    labels = {question.label for question in all_questions}
    superseded_labels = {"Race/Ethnicity": "Race/Ethnicity (Select all that apply)"}
    for answer in application.form_answers:
        question = questions.get(str(answer.question_id))
        if (
            question
            and question.label in superseded_labels
            and superseded_labels[question.label] in labels
        ):
            continue
        if (
            question
            and question.required
            and (
                answer.answer is None
                or answer.answer.strip() == ""
                or (
                    QuestionLabel.requires_affirmative_answer(question.label)
                    and answer.answer.strip().lower() == "false"
                )
            )
        ):
            raise ServiceError(
                status_code=400,
                detail=f"Required field not answered: {question.label}",
            )
    if (
        application.form_answer_files is None
        or application.form_answer_files.original_filename is None
    ):
        raise ServiceError(status_code=400, detail="Resume is required")

    applicant = session.exec(
        select(HackathonApplicant)
        .where(HackathonApplicant.application_id == application.application_id)
        .with_for_update()
    ).first()
    if applicant is None:
        raise ServiceError(status_code=404, detail="Application not found")
    if applicant.is_already_submitted():
        raise ServiceError(status_code=409, detail="Application already submitted")
    if not applicant.can_submit_application():
        raise ServiceError(status_code=403, detail="User not in valid state to submit")
    if not application.is_draft:
        raise ServiceError(
            status_code=409, detail="Application has already been submitted"
        )

    walk_in = applicant.status == StatusEnum.WALK_IN
    if applicant.status == StatusEnum.APPLYING:
        applicant.status = StatusEnum.APPLIED
    elif walk_in:
        applicant.status = StatusEnum.WALK_IN_SUBMITTED
    application.is_draft = False
    application.updated_at = datetime.now(timezone.utc)

    try:
        session.add(applicant)
        session.add(application)
        session.commit()
        session.refresh(applicant)
        session.refresh(application)
    except SQLAlchemyError as error:
        session.rollback()
        logger.exception("Failed to submit application %s", application.application_id)
        raise ServiceError(
            status_code=500,
            detail="Failed to submit application",
        ) from error

    schedule = enqueue or (lambda task, *args: task(*args))
    if walk_in:
        schedule(
            send_rsvp_safely,
            user.email,
            user.full_name,
            str(application.application_id),
        )
    else:
        schedule(
            send_email_safely,
            EmailTemplate.CONFIRMATION,
            user.email,
            EmailSubject.CONFIRMATION,
            EmailMessage.CONFIRMATION,
            {},
        )
    return "Success"
