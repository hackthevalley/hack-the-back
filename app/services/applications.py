from datetime import datetime, timezone

from sqlmodel import col, select
from sqlalchemy.exc import IntegrityError

from app.core.errors import ServiceError
from sqlmodel import Session
from app.core.orm import eager_load
from app.models.constants import QuestionLabel
from app.models.forms import (
    FormAnswer,
    FormAnswerFile,
    FormApplication,
    FormWindow,
    HackathonApplicant,
    FormQuestion,
    StatusEnum,
)
from app.models.user import AccountUser


def create_application(
    current_user: AccountUser,
    session: Session,
) -> FormApplication:
    if not all([current_user.first_name, current_user.last_name, current_user.email]):
        raise ServiceError(
            status_code=400,
            detail="User profile incomplete - missing first name, last name, or email",
        )
    if not all(
        [
            current_user.first_name.strip(),
            current_user.last_name.strip(),
            current_user.email.strip(),
        ]
    ):
        raise ServiceError(
            status_code=400,
            detail="User profile incomplete - first name, last name, or email cannot be empty",
        )

    questions = session.exec(
        select(FormQuestion).order_by(col(FormQuestion.question_order))
    ).all()

    application = FormApplication(
        user=current_user,
        is_draft=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    session.add(application)
    try:
        session.flush()
    except IntegrityError:
        # A concurrent request created this user's application first.
        session.rollback()
        existing_application = session.exec(
            select(FormApplication)
            .where(FormApplication.uid == current_user.uid)
            .options(
                eager_load(FormApplication.form_answers),
                eager_load(FormApplication.form_answer_files),
                eager_load(FormApplication.hacker_applicant),
            )
        ).first()
        if existing_application is None:
            raise
        return existing_application

    session.add(
        HackathonApplicant(
            applicant=application,
            status=StatusEnum.APPLYING,
        )
    )

    answers = []
    resume_question = None
    for question in questions:
        if QuestionLabel.contains_resume(question.label):
            resume_question = question
            continue

        answer_value = None
        label = question.label.lower().strip()
        if label == QuestionLabel.FIRST_NAME.value.lower():
            answer_value = current_user.first_name
        elif label == QuestionLabel.LAST_NAME.value.lower():
            answer_value = current_user.last_name
        elif label == QuestionLabel.EMAIL.value.lower():
            answer_value = current_user.email

        answers.append(
            FormAnswer(
                application_id=application.application_id,
                question_id=question.question_id,
                answer=answer_value,
            )
        )

    session.add_all(answers)
    if resume_question:
        session.add(
            FormAnswerFile(
                application_id=application.application_id,
                original_filename=None,
                file_path=None,
                question_id=resume_question.question_id,
            )
        )

    session.commit()
    session.refresh(current_user)

    statement = (
        select(FormApplication)
        .where(FormApplication.uid == current_user.uid)
        .options(
            eager_load(FormApplication.form_answers),
            eager_load(FormApplication.form_answer_files),
            eager_load(FormApplication.hacker_applicant),
        )
    )
    created_application = session.exec(statement).first()
    if created_application is None:
        raise RuntimeError("Application was created but could not be reloaded")
    return created_application


def is_valid_submission_time(session: Session, user: AccountUser | None = None) -> bool:
    if user and user.application and user.application.hacker_applicant:
        application_status = user.application.hacker_applicant.status
        if application_status == StatusEnum.WALK_IN:
            return True

    form = session.exec(select(FormWindow).limit(1)).first()
    if form is None:
        return False
    return form.start_at < datetime.now(timezone.utc) < form.end_at
