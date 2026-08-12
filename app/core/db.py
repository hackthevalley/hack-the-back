import inspect
import logging
from contextlib import contextmanager
from datetime import datetime, timezone
from functools import wraps
from typing import Annotated, Callable, List

from fastapi import Depends
from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlmodel import Session, col, create_engine, delete, select

from app.config import AppConfig, DatabaseConfig
from app.models.constants import QuestionLabel
from app.models.forms import (
    FormAnswer,
    FormAnswerFile,
    FormApplication,
    FormWindow,
    FormQuestion,
)
from app.models.meal import Meal

logger = logging.getLogger(__name__)


ADVISORY_LOCK_DATABASE_INIT = 123456786
ADVISORY_LOCK_FORM_TIME = 123456787
ADVISORY_LOCK_QUESTIONS = 123456788
ADVISORY_LOCK_MEALS = 123456789

DatabaseConfig.validate()

engine = create_engine(
    DatabaseConfig.URL,
    pool_size=DatabaseConfig.POOL_SIZE,
    max_overflow=DatabaseConfig.MAX_OVERFLOW,
    pool_pre_ping=DatabaseConfig.POOL_PRE_PING,
    pool_recycle=DatabaseConfig.POOL_RECYCLE_SECONDS,
    echo=False,
    connect_args={
        "connect_timeout": DatabaseConfig.CONNECT_TIMEOUT,
        "application_name": "hack-the-back",
        "keepalives": DatabaseConfig.KEEPALIVES,
        "keepalives_idle": DatabaseConfig.KEEPALIVES_IDLE,
        "keepalives_interval": DatabaseConfig.KEEPALIVES_INTERVAL,
        "keepalives_count": DatabaseConfig.KEEPALIVES_COUNT,
    },
)


def get_session():
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]


@contextmanager
def advisory_lock(session: Session, lock_id: int):
    if not isinstance(lock_id, int) or lock_id <= 0:
        raise ValueError(f"lock_id must be a positive integer, got: {lock_id}")

    # Session.commit() may release the session's connection back to its pool.
    # Hold a separate physical connection so PostgreSQL receives lock and
    # unlock on the same backend session regardless of commits inside `yield`.
    bind = session.get_bind()
    lock_engine = bind.engine if isinstance(bind, Connection) else bind
    with lock_engine.connect() as lock_connection:
        try:
            lock_connection.execute(
                text("SELECT pg_advisory_lock(:lock_id)"), {"lock_id": lock_id}
            )
            yield
        finally:
            lock_connection.execute(
                text("SELECT pg_advisory_unlock(:lock_id)"), {"lock_id": lock_id}
            )


def with_advisory_lock(lock_id: int):
    def decorator(func: Callable) -> Callable:
        sig = inspect.signature(func)

        @wraps(func)
        def wrapper(*args, **kwargs):
            bound = sig.bind(*args, **kwargs)
            session = bound.arguments.get("session")
            if session is None:
                raise ValueError(
                    f"Function {func.__name__} must have a 'session' parameter of type Session"
                )

            with advisory_lock(session, lock_id):
                return func(*args, **kwargs)

        return wrapper

    return decorator


@with_advisory_lock(ADVISORY_LOCK_QUESTIONS)
def seed_questions(questions: List, session: Session):
    try:
        added_questions: list[FormQuestion] = []
        existing_questions = {
            question.label: question
            for question in session.exec(select(FormQuestion)).all()
        }
        configured_labels = {question["label"] for question in questions}
        stale_question_ids = [
            question.question_id
            for label, question in existing_questions.items()
            if label not in configured_labels
        ]

        if stale_question_ids:
            session.exec(
                delete(FormAnswer).where(
                    col(FormAnswer.question_id).in_(stale_question_ids)
                )
            )
            session.exec(
                delete(FormAnswerFile).where(
                    col(FormAnswerFile.question_id).in_(stale_question_ids)
                )
            )
            session.exec(
                delete(FormQuestion).where(
                    col(FormQuestion.question_id).in_(stale_question_ids)
                )
            )

        for index, question in enumerate(questions):
            existing_question = existing_questions.get(question["label"])
            if existing_question is None:
                new_question = FormQuestion.model_validate(
                    question, update={"question_order": index}
                )
                session.add(new_question)
                added_questions.append(new_question)
                continue

            existing_question.question_order = index
            existing_question.required = question["required"]
            session.add(existing_question)

        if added_questions:
            session.flush()
            application_ids = session.exec(select(FormApplication.application_id)).all()
            session.add_all(
                [
                    FormAnswer(
                        application_id=application_id,
                        question_id=question.question_id,
                        answer=None,
                    )
                    for question in added_questions
                    if not QuestionLabel.contains_resume(question.label)
                    for application_id in application_ids
                ]
            )
            session.add_all(
                [
                    FormAnswerFile(
                        application_id=application_id,
                        question_id=question.question_id,
                        original_filename=None,
                        file_path=None,
                    )
                    for question in added_questions
                    if QuestionLabel.contains_resume(question.label)
                    for application_id in application_ids
                ]
            )

        session.commit()
    except Exception:
        session.rollback()
        raise


@with_advisory_lock(ADVISORY_LOCK_FORM_TIME)
def seed_form_time(session: Session):
    try:
        row = session.exec(select(FormWindow).limit(1)).first()
        current_time = datetime.now(timezone.utc)
        if row is None:
            row = FormWindow(
                created_at=current_time,
                updated_at=current_time,
                start_at=AppConfig.APPLICATION_START_DATE,
                end_at=AppConfig.APPLICATION_END_DATE,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
        # Existing values may have been changed live by an administrator.
        # Environment dates are defaults only and must never overwrite them.
    except Exception:
        session.rollback()
        raise


@with_advisory_lock(ADVISORY_LOCK_MEALS)
def seed_meals(meals: List, session: Session):
    try:
        existing_meals = set(session.exec(select(Meal.day, Meal.meal_type)).all())

        for meal_data in meals:
            key = (meal_data["day"], meal_data["meal_type"])
            if key not in existing_meals:
                session.add(
                    Meal(
                        day=meal_data["day"],
                        meal_type=meal_data["meal_type"],
                        is_active=meal_data.get("is_active", False),
                    )
                )
        session.commit()
    except Exception:
        session.rollback()
        raise
