from datetime import date, datetime, timezone
from unittest.mock import Mock

import pytest
from fastapi import HTTPException

from app.config import AppConfig
from app.models.forms import StatusEnum
from app.routers.account import rsvp_status_update


def test_rsvp_deadline_is_inclusive_and_enforced(monkeypatch):
    monkeypatch.setattr(AppConfig, "EVENT_START_DATE", datetime.fromisoformat("2026-10-16T00:00:00-04:00"))
    monkeypatch.setattr(AppConfig, "RSVP_DUE_DATE", date(2026, 10, 9))
    assert AppConfig.is_rsvp_open(datetime(2026, 10, 10, 3, 59, tzinfo=timezone.utc))
    assert not AppConfig.is_rsvp_open(datetime(2026, 10, 10, 4, 0, tzinfo=timezone.utc))

    monkeypatch.setattr(AppConfig, "RSVP_DUE_DATE", date(2000, 1, 1))
    with pytest.raises(HTTPException, match="RSVP deadline") as error:
        rsvp_status_update(StatusEnum.ACCEPTED_INVITE, Mock(), Mock())
    assert error.value.status_code == 403
