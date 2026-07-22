from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlmodel import col, select

from app.core.db import SessionDep
from app.core.orm import eager_load
from app.models.constants import QuestionLabel
from app.models.forms import (
    Forms_Answer,
    Forms_AnswerFile,
    Forms_Application,
    Forms_Form,
    Forms_HackathonApplicant,
    Forms_Question,
    StatusEnum,
)
from app.models.user import Account_User


def create_application(
    current_user: Account_User,
    session: SessionDep,
) -> Forms_Application:
    if not all([current_user.first_name, current_user.last_name, current_user.email]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User profile incomplete - missing first name, last name, or email",
        )
    if not all(
        [
            current_user.first_name.strip(),
            current_user.last_name.strip(),
            current_user.email.strip(),
        ]
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User profile incomplete - first name, last name, or email cannot be empty",
        )

    questions = session.exec(
        select(Forms_Question).order_by(col(Forms_Question.question_order))
    ).all()

    application = Forms_Application(
        user=current_user,
        is_draft=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    session.add(application)
    session.flush()

    session.add(
        Forms_HackathonApplicant(
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
            Forms_Answer(
                application_id=application.application_id,
                question_id=question.question_id,
                answer=answer_value,
            )
        )

    session.add_all(answers)
    if resume_question:
        session.add(
            Forms_AnswerFile(
                application_id=application.application_id,
                original_filename=None,
                file_path=None,
                question_id=resume_question.question_id,
            )
        )

    session.commit()
    session.refresh(current_user)

    statement = (
        select(Forms_Application)
        .where(Forms_Application.uid == current_user.uid)
        .options(
            eager_load(Forms_Application.form_answers),
            eager_load(Forms_Application.form_answersfile),
            eager_load(Forms_Application.hackathonapplicant),
        )
    )
    created_application = session.exec(statement).first()
    if created_application is None:
        raise RuntimeError("Application was created but could not be reloaded")
    return created_application


def is_valid_submission_time(session: SessionDep, user: Account_User | None = None):
    if user and user.application and user.application.hackathonapplicant:
        application_status = user.application.hackathonapplicant.status
        if application_status in [StatusEnum.WALK_IN, StatusEnum.WALK_IN_SUBMITTED]:
            return True

    form = session.exec(select(Forms_Form).limit(1)).first()
    if form is None:
        return False
    return form.start_at < datetime.now(timezone.utc) < form.end_at
