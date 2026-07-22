from contextlib import contextmanager

from app import main


def test_database_initialization_is_serialized(monkeypatch):
    events: list[str] = []
    fake_session = object()
    questions = [{"label": "example"}]

    class SessionContext:
        def __enter__(self):
            events.append("session-enter")
            return fake_session

        def __exit__(self, exc_type, exc_value, traceback):
            events.append("session-exit")

    @contextmanager
    def fake_advisory_lock(session, lock_id):
        assert session is fake_session
        assert lock_id == main.ADVISORY_LOCK_DATABASE_INIT
        events.append("lock-enter")
        try:
            yield
        finally:
            events.append("lock-exit")

    monkeypatch.setattr(main, "validate_config", lambda: events.append("validate"))
    monkeypatch.setattr(main, "load_form_questions", lambda: questions)
    monkeypatch.setattr(main, "Session", lambda engine: SessionContext())
    monkeypatch.setattr(main, "advisory_lock", fake_advisory_lock)
    monkeypatch.setattr(
        main,
        "seed_questions",
        lambda loaded_questions, session: events.append("seed-questions"),
    )
    monkeypatch.setattr(
        main, "seed_form_time", lambda session: events.append("seed-form-time")
    )
    monkeypatch.setattr(
        main, "seed_meals", lambda meals, session: events.append("seed-meals")
    )

    main.initialize_database()

    assert events == [
        "validate",
        "session-enter",
        "lock-enter",
        "seed-questions",
        "seed-form-time",
        "seed-meals",
        "lock-exit",
        "session-exit",
    ]
