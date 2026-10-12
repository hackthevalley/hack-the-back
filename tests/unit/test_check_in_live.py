import uuid

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine

from app.models.forms import HackathonApplicant, StatusEnum
from app.routers.volunteer import live
from app.services import check_in_live
from app.services.check_in_live import get_check_in_counts


def test_check_in_counts_separate_scanned_hackers_and_walk_ins():
    engine = create_engine("sqlite://")
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

    engine.dispose()


def test_live_counts_authenticates_and_sends_initial_totals(monkeypatch):
    monkeypatch.setattr(live, "authorize_staff", lambda _token: True)
    monkeypatch.setattr(
        check_in_live,
        "load_check_in_counts",
        lambda: {"scannedCount": 12, "walkinCount": 3},
    )
    app = FastAPI()
    app.include_router(live.router)

    with TestClient(app).websocket_connect("/live") as websocket:
        websocket.send_json({"token": "staff-token"})
        assert websocket.receive_json() == {
            "scannedCount": 12,
            "walkinCount": 3,
        }
