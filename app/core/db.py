import inspect
import logging
from contextlib import contextmanager
from datetime import datetime, timezone
from functools import wraps
from typing import Annotated, Callable, List

from fastapi import Depends
from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, SQLModel, create_engine, select

from app.config import AppConfig, DatabaseConfig
from app.models.forms import Forms_Form, Forms_Question
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


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)


@with_advisory_lock(ADVISORY_LOCK_QUESTIONS)
def seed_questions(questions: List, session: Session):
    try:
        existing_labels = set(session.exec(select(Forms_Question.label)).all())

        for index, question in enumerate(questions):
            if question["label"] not in existing_labels:
                db_question = Forms_Question.model_validate(
                    question, update={"question_order": index}
                )
                session.add(db_question)

        session.commit()
    except IntegrityError as e:
        session.rollback()
        logger.warning("Integrity error while seeding questions, skipping: %s", e)
    except Exception:
        session.rollback()
        raise


@with_advisory_lock(ADVISORY_LOCK_FORM_TIME)
def seed_form_time(session: Session):
    try:
        row = session.exec(select(Forms_Form).limit(1)).first()
        if row is None:
            current_time = datetime.now(timezone.utc)
            db_forms_form = Forms_Form(
                created_at=current_time,
                updated_at=current_time,
                start_at=AppConfig.APPLICATION_START_DATE,
                end_at=AppConfig.APPLICATION_END_DATE,
            )
            session.add(db_forms_form)
            session.commit()
            session.refresh(db_forms_form)
    except IntegrityError as e:
        session.rollback()
        logger.warning("Integrity error while seeding form time, skipping: %s", e)
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
    except IntegrityError as e:
        session.rollback()
        logger.warning("Integrity error while seeding meals, skipping: %s", e)
    except Exception:
        session.rollback()
        raise
