import uuid
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.core.db import get_session
from app.dependencies.auth import get_current_user
from app.models.constants import UserRole
from app.models.forms import HackathonApplicant, StatusEnum
from app.routers import router
from app.services.check_ins import get_check_in_counts


def test_check_in_counts_separate_scanned_hackers_and_walk_ins():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        session.add_all(
            [
                HackathonApplicant(application_id=uuid.uuid4(), status=status)
                for status in (
                    StatusEnum.SCANNED_IN,
                    StatusEnum.WALK_IN,
                    StatusEnum.WALK_IN_SUBMITTED,
                    StatusEnum.ACCEPTED_INVITE,
                )
            ]
        )
        session.commit()

        assert get_check_in_counts(session) == {
            "scannedCount": 1,
            "walkinCount": 2,
        }

        app = FastAPI()
        app.include_router(router, prefix="/api")
        app.dependency_overrides[get_session] = lambda: session
        endpoint = "/api/volunteer/check-ins/counts"
        with TestClient(app) as client:
            assert client.get(endpoint).status_code == 401
            user = SimpleNamespace(role=UserRole.HACKER)
            app.dependency_overrides[get_current_user] = lambda: user
            assert client.get(endpoint).status_code == 403
            for role in (UserRole.VOLUNTEER, UserRole.ADMIN):
                user.role = role
                response = client.get(endpoint)
                assert response.status_code == 200
                assert response.json() == {"scannedCount": 1, "walkinCount": 2}

    engine.dispose()
