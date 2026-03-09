import inspect
import logging
from contextlib import contextmanager
from datetime import datetime, timezone
from functools import wraps
from typing import Annotated, Callable, List

from fastapi import Depends
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, SQLModel, create_engine, select

from app.config import AppConfig, DatabaseConfig
from app.models.forms import Forms_Form, Forms_Question
from app.models.meal import Meal

logger = logging.getLogger(__name__)

# PostgreSQL advisory lock IDs for preventing race conditions during seeding
# These are arbitrary positive integers used to coordinate access across multiple workers
# Lock ID range: Using 123456700-123456799 for application-specific locks
ADVISORY_LOCK_FORM_TIME = 123456787  # Protects form time seeding operations
ADVISORY_LOCK_QUESTIONS = 123456788  # Protects question seeding operations
ADVISORY_LOCK_MEALS = 123456789  # Protects meal seeding operations

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
    """
    Context manager for PostgreSQL advisory locks.

    Ensures locks are always properly released, even if an exception occurs.
    Uses parameterized queries to prevent SQL injection.

    Args:
        session: Database session
        lock_id: Unique integer identifier for this lock (must be positive)

    Raises:
        ValueError: If lock_id is not a positive integer

    Example:
        with advisory_lock(session, ADVISORY_LOCK_QUESTIONS):
            # Critical section - only one worker can execute this
            perform_seeding()
    """
    if not isinstance(lock_id, int) or lock_id <= 0:
        raise ValueError(f"lock_id must be a positive integer, got: {lock_id}")

    try:
        session.execute(text("SELECT pg_advisory_lock(:lock_id)"), {"lock_id": lock_id})
        yield
    finally:
        session.execute(
            text("SELECT pg_advisory_unlock(:lock_id)"), {"lock_id": lock_id}
        )


def with_advisory_lock(lock_id: int):
    """
    Decorator for functions that need PostgreSQL advisory locks.

    Args:
        lock_id: Unique integer identifier for this lock

    Example:
        @with_advisory_lock(ADVISORY_LOCK_QUESTIONS)
        def seed_questions(questions: List, session: Session):
            # This will be wrapped with advisory lock
            pass
    """

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
    """
    Seed form questions into the database with proper locking.
    """
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
    """Seed application form timeline into the database."""
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
    """
    Seed hackathon meals into the database with proper locking.
    """
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
