import os
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from typing import Annotated, List

from fastapi import Depends
from sqlmodel import Session, SQLModel, create_engine, select

from app.models.forms import Forms_Form, Forms_Question

DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL)


# Dependency for using the database session
def get_session():
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]


# Initialize the database
def create_db_and_tables():
    SQLModel.metadata.create_all(engine)


def seed_questions(questions: List, session: Session):
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
            session.refresh(db_question)


def seed_form_time(session: Session):
    row = session.exec(select(Forms_Form).limit(1)).first()
    if row is None:
        current_time = datetime.now(ZoneInfo("America/New_York"))
        created_at = current_time
        updated_at = current_time
        start_at = datetime(2025, 6, 1, 0, 0, 0, tzinfo=timezone(timedelta(hours=-4)))
        end_at = datetime(2025, 9, 1, 0, 0, 0, tzinfo=timezone(timedelta(hours=-4)))
        db_forms_form = Forms_Form(created_at=created_at, updated_at=updated_at, start_at=start_at, end_at=end_at)
        
        session.add(db_forms_form)
        session.commit()
        session.refresh(db_forms_form)
