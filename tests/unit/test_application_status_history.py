from datetime import datetime, timezone
from unittest.mock import Mock

import pytest
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, SQLModel, create_engine, select

from app.core.errors import ServiceError
from app.models.forms import ApplicationStatusHistory, FormApplication, HackathonApplicant, StatusEnum
from app.models.user import AccountUser
from app.models.constants import UserRole
from app.services.admin_applications import get_application_detail, update_application_status


@pytest.fixture
def records():
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        admin = AccountUser(first_name="Admin", last_name="One", email="admin@example.com",
                            password="unused", role=UserRole.ADMIN, is_active=True)
        session.add(admin)
        session.flush()
        now = datetime.now(timezone.utc)
        application = FormApplication(uid=admin.uid, is_draft=False, created_at=now, updated_at=now)
        session.add(application)
        session.flush()
        session.add(HackathonApplicant(application_id=application.application_id, status=StatusEnum.APPLIED))
        session.commit()
        yield session, application.application_id, admin
    engine.dispose()


def test_decisions_preserve_actor_and_transitions(records):
    session, application_id, admin = records
    enqueue = Mock()
    for status in (StatusEnum.ACCEPTED, StatusEnum.ACCEPTED, StatusEnum.WAITLISTED, StatusEnum.REJECTED):
        update_application_status(session, application_id, status, enqueue, admin=admin)
    history = get_application_detail(session, application_id)["status_history"]
    assert len(history) == 3
    assert [(entry.previous_status, entry.new_status) for entry in reversed(history)] == [
        ("APPLIED", "ACCEPTED"), ("ACCEPTED", "WAITLISTED"), ("WAITLISTED", "REJECTED")
    ]
    assert all(entry.admin_id == admin.uid and entry.admin_email == admin.email
               and entry.admin_name == "Admin One" and entry.changed_at for entry in history)
    enqueue.assert_called_once()


def test_failed_commit_rolls_back_decision_and_history(records, monkeypatch):
    session, application_id, admin = records
    enqueue = Mock()
    monkeypatch.setattr(session, "commit", Mock(side_effect=SQLAlchemyError("failure")))
    with pytest.raises(ServiceError):
        update_application_status(session, application_id, StatusEnum.ACCEPTED, enqueue, admin=admin)
    assert session.get(HackathonApplicant, application_id).status == StatusEnum.APPLIED
    assert session.exec(select(ApplicationStatusHistory)).all() == []
    enqueue.assert_not_called()
