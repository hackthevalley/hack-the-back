from datetime import datetime, timedelta, timezone

from app.config import AppConfig
from app.core.db import seed_form_time
from app.models.forms import FormWindow


class FirstResult:
    def __init__(self, row: FormWindow | None):
        self.row = row

    def first(self):
        return self.row


class FakeSession:
    def __init__(self, row: FormWindow | None):
        self.row = row
        self.added: list[FormWindow] = []
        self.commit_count = 0
        self.refreshed: list[FormWindow] = []

    def exec(self, _statement):
        return FirstResult(self.row)

    def add(self, row: FormWindow):
        self.added.append(row)

    def commit(self):
        self.commit_count += 1

    def refresh(self, row: FormWindow):
        self.refreshed.append(row)


def run_seed(session: FakeSession):
    seed_form_time.__wrapped__(session=session)  # type: ignore[attr-defined, arg-type]


def test_form_time_seed_creates_missing_row():
    session = FakeSession(None)

    run_seed(session)

    assert session.commit_count == 1
    assert session.refreshed == session.added
    assert len(session.added) == 1
    assert session.added[0].start_at == AppConfig.APPLICATION_START_DATE
    assert session.added[0].end_at == AppConfig.APPLICATION_END_DATE


def test_form_time_seed_does_not_write_when_dates_match():
    original_updated_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    row = FormWindow(
        created_at=original_updated_at,
        updated_at=original_updated_at,
        start_at=AppConfig.APPLICATION_START_DATE,
        end_at=AppConfig.APPLICATION_END_DATE,
    )
    session = FakeSession(row)

    run_seed(session)

    assert session.added == []
    assert session.commit_count == 0
    assert session.refreshed == []
    assert row.updated_at == original_updated_at


def test_form_time_seed_updates_existing_row(monkeypatch):
    original_updated_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    row = FormWindow(
        created_at=original_updated_at,
        updated_at=original_updated_at,
        start_at=AppConfig.APPLICATION_START_DATE,
        end_at=AppConfig.APPLICATION_END_DATE,
    )
    new_start = AppConfig.APPLICATION_START_DATE + timedelta(days=1)
    new_end = AppConfig.APPLICATION_END_DATE + timedelta(days=1)
    monkeypatch.setattr(AppConfig, "APPLICATION_START_DATE", new_start)
    monkeypatch.setattr(AppConfig, "APPLICATION_END_DATE", new_end)
    session = FakeSession(row)

    run_seed(session)

    assert row.start_at == new_start
    assert row.end_at == new_end
    assert row.updated_at > original_updated_at
    assert session.added == [row]
    assert session.commit_count == 1
    assert session.refreshed == [row]
