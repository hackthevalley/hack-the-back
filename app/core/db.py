import os
from datetime import datetime, timedelta, timezone
from typing import Annotated, List
from zoneinfo import ZoneInfo

from fastapi import Depends
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, SQLModel, create_engine, select

from app.models.forms import Forms_Form, Forms_Question
from app.models.meal import Meal

DATABASE_URL = os.getenv("DATABASE_URL")

# Configure connection pooling for better performance
engine = create_engine(
    DATABASE_URL,
    # Connection pool settings
    pool_size=20,  # Number of connections to maintain in pool
    max_overflow=10,  # Maximum overflow connections beyond pool_size
    pool_pre_ping=True,  # Verify connections before using them
    pool_recycle=3600,  # Recycle connections after 1 hour
    echo=False,  # Set to True for SQL query logging (debug only)
    connect_args={
        "connect_timeout": 10,
        "application_name": "hack-the-back",
        # Connection pooling at the driver level
        "keepalives": 1,
        "keepalives_idle": 30,
        "keepalives_interval": 5,
        "keepalives_count": 5,
    },
)


# Dependency for using the database session
def get_session():
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]


# Initialize the database
def create_db_and_tables():
    SQLModel.metadata.create_all(engine)


def seed_questions(questions: List, session: Session):
    # Use advisory lock to ensure only one worker seeds at a time
    lock_id = 123456788  # Unique ID for question seeding

    try:
        # Acquire a PostgreSQL advisory lock - this blocks other workers
        session.execute(text("SELECT pg_advisory_lock(:lock_id)"), {"lock_id": lock_id})

        for index, question in enumerate(questions):
            statement = select(Forms_Question).where(
                Forms_Question.label == question["label"]
            )
            selected_question = session.exec(statement).first()
            if not selected_question:
                try:
                    db_question = Forms_Question.model_validate(
                        question, update={"question_order": index}
                    )
                    session.add(db_question)
                    session.commit()
                    session.refresh(db_question)
                except IntegrityError:
                    # Question was inserted by another worker, rollback and continue
                    session.rollback()
    finally:
        # Release the advisory lock
        session.execute(
            text("SELECT pg_advisory_unlock(:lock_id)"), {"lock_id": lock_id}
        )


def seed_form_time(session: Session):
    row = session.exec(select(Forms_Form).limit(1)).first()
    if row is None:
        current_time = datetime.now(ZoneInfo("America/New_York"))
        created_at = current_time
        updated_at = current_time
        start_at = datetime(2025, 6, 1, 0, 0, 0, tzinfo=timezone(timedelta(hours=-4)))
        end_at = datetime(2025, 9, 1, 0, 0, 0, tzinfo=timezone(timedelta(hours=-4)))
        db_forms_form = Forms_Form(
            created_at=created_at,
            updated_at=updated_at,
            start_at=start_at,
            end_at=end_at,
        )

        session.add(db_forms_form)
        session.commit()
        session.refresh(db_forms_form)


def seed_meals(meals: List, session: Session):
    """Seed meals into the database if they don't exist"""
    # Use advisory lock to ensure only one worker seeds at a time
    # Lock ID: arbitrary number to identify this specific seeding operation
    lock_id = 123456789  # Unique ID for meal seeding

    try:
        # Acquire a PostgreSQL advisory lock - this blocks other workers
        session.execute(text("SELECT pg_advisory_lock(:lock_id)"), {"lock_id": lock_id})

        for meal_data in meals:
            # Check if meal already exists
            statement = select(Meal).where(
                Meal.day == meal_data["day"], Meal.meal_type == meal_data["meal_type"]
            )
            existing_meal = session.exec(statement).first()

            if not existing_meal:
                try:
                    db_meal = Meal(
                        day=meal_data["day"],
                        meal_type=meal_data["meal_type"],
                        is_active=meal_data.get("is_active", False),
                    )
                    session.add(db_meal)
                    session.commit()
                except IntegrityError:
                    # Meal was inserted by another worker, rollback and continue
                    session.rollback()
    finally:
        # Release the advisory lock
        session.execute(
            text("SELECT pg_advisory_unlock(:lock_id)"), {"lock_id": lock_id}
        )
