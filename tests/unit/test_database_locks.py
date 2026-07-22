from app.core.db import advisory_lock


def test_advisory_lock_uses_same_dedicated_connection_for_unlock():
    calls: list[tuple[str, dict[str, int]]] = []

    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return None

        def execute(self, statement, parameters):
            calls.append((str(statement), parameters))

    connection = FakeConnection()

    class FakeEngine:
        def connect(self):
            return connection

    class FakeSession:
        def get_bind(self):
            return FakeEngine()

    with advisory_lock(FakeSession(), 123):  # type: ignore[arg-type]
        calls.append(("critical section", {}))

    assert calls == [
        ("SELECT pg_advisory_lock(:lock_id)", {"lock_id": 123}),
        ("critical section", {}),
        ("SELECT pg_advisory_unlock(:lock_id)", {"lock_id": 123}),
    ]
