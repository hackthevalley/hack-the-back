import os
import subprocess
import time
import uuid
from datetime import timedelta
from pathlib import Path

import httpx
import jwt
import psycopg2
import pytest


ROOT = Path(__file__).resolve().parents[2]
COMPOSE = [
    "docker",
    "compose",
    "-p",
    "hack-the-back-e2e",
    "-f",
    str(ROOT / "docker-compose.e2e.yml"),
]
API_URL = os.getenv("E2E_API_URL", "http://127.0.0.1:58000")
MAIL_URL = os.getenv("E2E_MAIL_URL", "http://127.0.0.1:58080")
DATABASE_URL = os.getenv(
    "E2E_DATABASE_URL",
    "postgresql://postgres:postgres@127.0.0.1:55432/hack_the_back_e2e",
)
SECRET = "e2e-only-secret-key-not-for-production"
PASSWORD = "CorrectHorseBatteryStaple!42"
PASSWORD_HASH = "$2b$04$aINO.uxUOdITehDsZzp7YepCdzSmdCeO40EnGqdeBWkCWRi5CDFzy"


def pytest_addoption(parser):
    parser.addoption(
        "--e2e-no-compose",
        action="store_true",
        help="Use an already-running E2E API instead of managing Docker Compose",
    )


def pytest_collection_modifyitems(items):
    for item in items:
        if Path(__file__).parent in Path(item.path).parents:
            item.add_marker(pytest.mark.e2e)


@pytest.fixture(scope="session", autouse=True)
def e2e_stack(request):
    if request.config.getoption("--e2e-no-compose"):
        _wait_for_api()
        yield
        return

    coverage_dir = ROOT / "test-artifacts" / "coverage"
    coverage_dir.mkdir(parents=True, exist_ok=True)
    (coverage_dir / ".coverage.e2e").unlink(missing_ok=True)
    up_command = COMPOSE + ["up", "--wait"]
    if os.getenv("E2E_SKIP_BUILD") != "1":
        up_command.insert(-1, "--build")
    subprocess.run(up_command, cwd=ROOT, check=True)
    try:
        _wait_for_api()
        yield
    finally:
        subprocess.run(COMPOSE + ["down", "--volumes", "--remove-orphans"], cwd=ROOT)


def _wait_for_api():
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        try:
            if httpx.get(f"{API_URL}/health", timeout=2).status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.5)
    raise RuntimeError(f"E2E API did not become ready at {API_URL}")


def db_query(sql: str) -> list[str]:
    with psycopg2.connect(DATABASE_URL) as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql)
            if cursor.description is None:
                return []
            return [
                "|".join(
                    "t" if value is True else "f" if value is False else str(value)
                    for value in row
                )
                for row in cursor.fetchall()
            ]


@pytest.fixture(scope="session")
def client():
    with httpx.Client(base_url=API_URL, timeout=15) as value:
        yield value


@pytest.fixture(autouse=True)
def clear_mail():
    httpx.delete(f"{MAIL_URL}/messages")


def token(
    email: str,
    scopes: list[str] | None = None,
    expires: timedelta | None = None,
    token_version: int = 0,
):
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    payload = {
        "sub": email,
        "scopes": scopes or [],
        "ver": token_version,
        # Avoid a one-second host/container clock-boundary race in PyJWT's iat check.
        "iat": now - timedelta(seconds=5),
        "exp": now + (expires or timedelta(minutes=10)),
    }
    return jwt.encode(payload, SECRET, algorithm="HS256")


@pytest.fixture
def unique_email(request):
    return f"{request.node.name}-{time.time_ns()}@example.com"


def _identity(role: str, email: str | None = None):
    email = email or f"e2e-{role.lower()}-{time.time_ns()}@example.com"
    db_query(
        "INSERT INTO account_user "
        "(first_name, last_name, email, uid, password, role, is_active, "
        "token_version, failed_login_attempts) VALUES "
        f"('E2E', '{role.title()}', '{email}', '{uuid.uuid4()}', "
        f"'{PASSWORD_HASH}', '{role}', true, 0, 0)"
    )
    scopes = [role.lower()] if role in {"ADMIN", "VOLUNTEER"} else []
    access_token = token(email, scopes)
    return {
        "email": email,
        "headers": {"Authorization": f"Bearer {access_token}"},
    }


@pytest.fixture
def active_hacker(unique_email):
    identity = _identity("HACKER", unique_email)
    identity.update({"password": PASSWORD, "token_version": 0})
    return identity


@pytest.fixture
def admin_identity():
    return _identity("ADMIN")


@pytest.fixture(scope="session")
def admin_headers():
    return _identity("ADMIN")["headers"]


@pytest.fixture(scope="session")
def volunteer_headers():
    return _identity("VOLUNTEER")["headers"]
