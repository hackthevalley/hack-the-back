from datetime import timedelta

import pytest
from fastapi import HTTPException

from app.config import AppConfig
from app.routers.admin.schedule import validate_event_window


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
