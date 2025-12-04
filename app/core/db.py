from contextlib import contextmanager
from datetime import datetime
from typing import Annotated, List
from zoneinfo import ZoneInfo

from fastapi import Depends
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, SQLModel, create_engine, select

from app.config import AppConfig, DatabaseConfig
from app.models.forms import Forms_Form, Forms_Question
from app.models.meal import Meal

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


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)


def seed_questions(questions: List, session: Session):
    """
    Seed form questions into the database with proper locking.
    """
    with advisory_lock(session, ADVISORY_LOCK_QUESTIONS):
        try:
            for index, question in enumerate(questions):
                statement = select(Forms_Question).where(
                    Forms_Question.label == question["label"]
                )
                selected_question = session.exec(statement).first()

                if not selected_question:
                    db_question = Forms_Question.model_validate(
                        question, update={"question_order": index}
                    )
                    session.add(db_question)

            session.commit()
        except IntegrityError:
            session.rollback()
        except Exception:
            session.rollback()
            raise


def seed_form_time(session: Session):
    """Seed application form timeline into the database."""
    row = session.exec(select(Forms_Form).limit(1)).first()
    if row is None:
        current_time = datetime.now(ZoneInfo("America/New_York"))
        db_forms_form = Forms_Form(
            created_at=current_time,
            updated_at=current_time,
            start_at=AppConfig.APPLICATION_START_DATE,
            end_at=AppConfig.APPLICATION_END_DATE,
        )

        session.add(db_forms_form)
        session.commit()
        session.refresh(db_forms_form)


def seed_meals(meals: List, session: Session):
    """
    Seed hackathon meals into the database with proper locking.
    """
    with advisory_lock(session, ADVISORY_LOCK_MEALS):
        try:
            for meal_data in meals:
                statement = select(Meal).where(
                    Meal.day == meal_data["day"],
                    Meal.meal_type == meal_data["meal_type"],
                )
                existing_meal = session.exec(statement).first()

                if not existing_meal:
                    db_meal = Meal(
                        day=meal_data["day"],
                        meal_type=meal_data["meal_type"],
                        is_active=meal_data.get("is_active", False),
                    )
                    session.add(db_meal)
            session.commit()
        except IntegrityError:
            session.rollback()
        except Exception:
            session.rollback()
            raise
