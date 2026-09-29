import uuid
from datetime import timedelta

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlmodel import Session, create_engine

from app.config import AppConfig
from app.models.schedule import ScheduleEvent, utc_now
from app.routers.admin.schedule import (
    create_event,
    delete_event,
    get_event_or_404,
    list_events,
    update_event,
    validate_event_window,
)
from app.routers.schedule import get_schedule
from app.schemas.schedule import ScheduleEventCreate, ScheduleEventUpdate


def test_schedule_event_accepts_configured_event_window():
    validate_event_window(AppConfig.EVENT_START_DATE, AppConfig.EVENT_END_DATE)


@pytest.mark.parametrize(
    ("starts_at", "ends_at"),
    [
        (
            AppConfig.EVENT_START_DATE - timedelta(minutes=1),
            AppConfig.EVENT_START_DATE + timedelta(minutes=30),
        ),
        (
            AppConfig.EVENT_END_DATE - timedelta(minutes=30),
            AppConfig.EVENT_END_DATE + timedelta(minutes=1),
        ),
        (AppConfig.EVENT_START_DATE, AppConfig.EVENT_START_DATE),
    ],
)
def test_schedule_event_rejects_invalid_windows(starts_at, ends_at):
    with pytest.raises(HTTPException) as error:
        validate_event_window(starts_at, ends_at)

    assert error.value.status_code == 422


def test_schedule_event_requires_timezone_aware_times():
    with pytest.raises(HTTPException, match="timezone"):
        validate_event_window(
            AppConfig.EVENT_START_DATE.replace(tzinfo=None),
            AppConfig.EVENT_END_DATE.replace(tzinfo=None),
        )


def test_schedule_schema_cleans_text_and_rejects_blank_title():
    payload = ScheduleEventCreate(
        title="  Opening ceremony  ",
        description="   ",
        location=None,
        starts_at=AppConfig.EVENT_START_DATE,
        ends_at=AppConfig.EVENT_START_DATE + timedelta(hours=1),
    )

    assert payload.title == "Opening ceremony"
    assert payload.description is None
    assert payload.location is None

    with pytest.raises(ValidationError, match="Title cannot be blank"):
        ScheduleEventCreate(
            title="   ",
            starts_at=AppConfig.EVENT_START_DATE,
            ends_at=AppConfig.EVENT_START_DATE + timedelta(hours=1),
        )


def test_schedule_crud_and_public_schedule():
    engine = create_engine("sqlite://")
    ScheduleEvent.__table__.create(engine)
    start = AppConfig.EVENT_START_DATE + timedelta(hours=2)
    end = start + timedelta(hours=1)

    with Session(engine) as session:
        created = create_event(
            ScheduleEventCreate(
                title="Workshop",
                description="Build something",
                location="Room 101",
                starts_at=start,
                ends_at=end,
            ),
            session,
        )

        assert created.id is not None
        assert [event.id for event in list_events(session)] == [created.id]

        public_schedule = get_schedule(session)
        assert public_schedule.event_start_at == AppConfig.EVENT_START_DATE
        assert public_schedule.event_end_at == AppConfig.EVENT_END_DATE
        assert [event.id for event in public_schedule.events] == [created.id]

        original_updated_at = created.updated_at
        updated = update_event(
            created.id,
            ScheduleEventUpdate(
                title="Updated workshop",
                description=None,
                location="Room 202",
                starts_at=start + timedelta(minutes=30),
                ends_at=end + timedelta(minutes=30),
            ),
            session,
        )
        assert updated.title == "Updated workshop"
        assert updated.location == "Room 202"
        assert updated.updated_at >= original_updated_at

        response = delete_event(created.id, session)
        assert response.status_code == 204
        assert list_events(session) == []

        with pytest.raises(HTTPException) as error:
            get_event_or_404(session, created.id)
        assert error.value.status_code == 404

    engine.dispose()


def test_schedule_model_uses_utc_timestamps():
    before = utc_now()
    event = ScheduleEvent(
        title="Demo",
        starts_at=AppConfig.EVENT_START_DATE,
        ends_at=AppConfig.EVENT_START_DATE + timedelta(minutes=30),
    )

    assert event.created_at >= before
    assert event.updated_at >= before


def test_schedule_get_event_returns_existing_event():
    event = ScheduleEvent(
        id=uuid.uuid4(),
        title="Demo",
        starts_at=AppConfig.EVENT_START_DATE,
        ends_at=AppConfig.EVENT_START_DATE + timedelta(minutes=30),
    )

    class FakeSession:
        def get(self, _model, event_id):
            assert event_id == event.id
            return event

    assert get_event_or_404(FakeSession(), event.id) is event  # type: ignore[arg-type]
