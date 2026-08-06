from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlmodel import Session, select

from app.core.orm import eager_load
from app.models.constants import EmailMessage, EmailSubject, EmailTemplate, QuestionLabel
from app.models.forms import (
    Forms_Answer,
    Forms_AnswerUpdate,
    Forms_Application,
    Forms_HackathonApplicant,
    Forms_Question,
    StatusEnum,
)
from app.models.user import Account_User
from app.services.applications import create_application, is_valid_submission_time
from app.services.email import send_email, send_rsvp
from app.validators import validate_profile_url


def get_or_create_application(session: Session, user: Account_User) -> dict:
    if user.application is None:
        if not is_valid_submission_time(session, user):
            raise HTTPException(status_code=404, detail="Submitting outside submission time")
        application = create_application(user, session)
    else:
        application = session.exec(
            select(Forms_Application)
            .where(Forms_Application.uid == user.uid)
            .options(
                eager_load(Forms_Application.form_answers),
                eager_load(Forms_Application.form_answersfile),
                eager_load(Forms_Application.hackathonapplicant),
            )
        ).first()
    if application is None:
        raise HTTPException(status_code=404, detail="Application not found")
    return {
        "application": application,
        "form_answers": application.form_answers,
        "form_answersfile": application.form_answersfile.original_filename
        if application.form_answersfile
        else None,
    }


def save_answers(
    session: Session,
    user: Account_User,
    updates: list[Forms_AnswerUpdate],
) -> dict:
    if not is_valid_submission_time(session, user):
        raise HTTPException(status_code=403, detail="Submission is currently closed")
    if user.application is None:
        user.application = create_application(user, session)

    application = session.exec(
        select(Forms_Application)
        .where(Forms_Application.uid == user.uid)
        .options(eager_load(Forms_Application.form_answers))
    ).first()
    if application is None:
        raise HTTPException(status_code=404, detail="Application not found")

    answers = {str(answer.question_id): answer for answer in application.form_answers}
    questions = {
        str(question.question_id): question
        for question in session.exec(select(Forms_Question)).all()
    }
    bulk_updates: list[dict] = []
    for update in updates:
        answer = answers.get(update.question_id)
        if answer is None:
            raise HTTPException(
                status_code=400, detail=f"Invalid question_id: {update.question_id}"
            )
        question = questions.get(update.question_id)
        if question:
            if (
                QuestionLabel.is_prefilled_field(question.label)
                and answer.answer
                and answer.answer.strip()
                and (not update.answer or not update.answer.strip())
            ):
                continue
            try:
                validate_profile_url(question.label, update.answer)
            except ValueError as error:
                raise HTTPException(status_code=400, detail=str(error)) from error
        bulk_updates.append({"id": answer.id, "answer": update.answer})

    try:
        if bulk_updates:
            session.bulk_update_mappings(Forms_Answer, bulk_updates)
        application.updated_at = datetime.now(timezone.utc)
        session.add(application)
        session.commit()
        session.refresh(application)
    except Exception as error:
        session.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to save answers: {error}"
        ) from error
    return {"message": "Answers saved successfully", "updated_count": len(bulk_updates)}


def submit_application(session: Session, user: Account_User) -> str:
    if not is_valid_submission_time(session, user):
        raise HTTPException(status_code=403, detail="Submission is currently closed")
    application = user.application
    if application is None:
        raise HTTPException(status_code=404, detail="Application not found")

    all_questions = session.exec(select(Forms_Question)).all()
    questions = {str(question.question_id): question for question in all_questions}
    labels = {question.label for question in all_questions}
    superseded_labels = {
        "Race/Ethnicity": "Race/Ethnicity (Select all that apply)"
    }
    for answer in application.form_answers:
        question = questions.get(str(answer.question_id))
        if (
            question
            and question.label in superseded_labels
            and superseded_labels[question.label] in labels
        ):
            continue
        if question and question.required and (
            answer.answer is None
            or answer.answer.strip() == ""
            or answer.answer == "false"
        ):
            raise HTTPException(
                status_code=400,
                detail=f"Required field not answered: {question.label}",
            )
    if (
        application.form_answersfile is None
        or application.form_answersfile.original_filename is None
    ):
        raise HTTPException(status_code=400, detail="Resume is required")

    applicant = session.exec(
        select(Forms_HackathonApplicant)
        .where(
            Forms_HackathonApplicant.application_id == application.application_id
        )
        .with_for_update()
    ).first()
    if applicant is None:
        raise HTTPException(status_code=404, detail="Application not found")
    if applicant.is_already_submitted():
        raise HTTPException(status_code=409, detail="Application already submitted")
    if not applicant.can_submit_application():
        raise HTTPException(status_code=403, detail="User not in valid state to submit")

    walk_in = applicant.status == StatusEnum.WALK_IN
    if applicant.status == StatusEnum.APPLYING:
        applicant.status = StatusEnum.APPLIED
    elif walk_in:
        applicant.status = StatusEnum.WALK_IN_SUBMITTED
    if not application.is_draft:
        raise HTTPException(status_code=409, detail="Application has already been submitted")
    application.is_draft = False
    application.updated_at = datetime.now(timezone.utc)

    try:
        session.add(applicant)
        session.add(application)
        session.commit()
        session.refresh(applicant)
        session.refresh(application)
    except Exception as error:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to submit application: {error}",
        ) from error

    if walk_in:
        send_rsvp(user.email, user.full_name, str(application.application_id))
    else:
        send_email(
            EmailTemplate.CONFIRMATION,
            user.email,
            EmailSubject.CONFIRMATION,
            EmailMessage.CONFIRMATION,
            {},
        )
    return "Success"
