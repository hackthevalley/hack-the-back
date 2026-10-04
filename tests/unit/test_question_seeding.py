from contextlib import nullcontext
from datetime import datetime, timezone

from sqlmodel import Session, SQLModel, create_engine, select

from app.core import db
from app.models.constants import UserRole
from app.models.forms import FormAnswer, FormApplication, FormQuestion
from app.models.user import AccountUser


def test_removed_questions_become_inactive_without_deleting_answers(monkeypatch):
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(db, "advisory_lock", lambda *_args: nullcontext())

    with Session(engine) as session:
        user = AccountUser(
            first_name="Test",
            last_name="User",
            email="test@example.com",
            password="unused",
            role=UserRole.HACKER,
            is_active=True,
        )
        session.add(user)
        session.flush()
        now = datetime.now(timezone.utc)
        application = FormApplication(
            uid=user.uid, is_draft=False, created_at=now, updated_at=now
        )
        question = FormQuestion(question_order=0, label="Removed", required=True)
        session.add_all([application, question])
        session.flush()
        answer = FormAnswer(
            application_id=application.application_id,
            question_id=question.question_id,
            answer="Keep me",
        )
        session.add(answer)
        session.commit()

        db.seed_questions([], session)

        session.refresh(question)
        assert question.is_active is False
        assert session.exec(select(FormAnswer)).one().answer == "Keep me"

    engine.dispose()
