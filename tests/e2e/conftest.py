import os
import subprocess
import time
from datetime import timedelta
from pathlib import Path

import httpx
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
SECRET = "e2e-only-secret-key-not-for-production"
PASSWORD = "CorrectHorseBatteryStaple!42"


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
            if httpx.get(f"{API_URL}/", timeout=2).status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.5)
    raise RuntimeError(f"E2E API did not become ready at {API_URL}")


def db_query(sql: str) -> list[str]:
    result = subprocess.run(
        COMPOSE
        + [
            "exec",
            "-T",
            "e2e-db",
            "psql",
            "-U",
            "postgres",
            "-d",
            "hack_the_back_e2e",
            "-At",
            "-c",
            sql,
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return [line for line in result.stdout.splitlines() if line]


def restart_api():
    subprocess.run(COMPOSE + ["restart", "e2e-api"], cwd=ROOT, check=True)
    _wait_for_api()


@pytest.fixture
def client():
    with httpx.Client(base_url=API_URL, timeout=15) as value:
        yield value


@pytest.fixture(autouse=True)
def clear_mail():
    httpx.delete(f"{MAIL_URL}/messages")


def token(email: str, scopes: list[str] | None = None, expires: timedelta | None = None):
    import jwt
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    payload = {
        "sub": email,
        "scopes": scopes or [],
        # Avoid a one-second host/container clock-boundary race in PyJWT's iat check.
        "iat": now - timedelta(seconds=5),
        "exp": now + (expires or timedelta(minutes=10)),
    }
    return jwt.encode(payload, SECRET, algorithm="HS256")


@pytest.fixture
def unique_email(request):
    return f"{request.node.name}-{time.time_ns()}@example.com"


@pytest.fixture
def active_hacker(client, unique_email):
    response = client.post(
        "/api/account/users",
        json={
            "first_name": "E2E",
            "last_name": "Hacker",
            "email": unique_email,
            "password": PASSWORD,
        },
    )
    assert response.status_code == 201, response.text
    activation = token(unique_email, ["account_activate"])
    response = client.post(
        "/api/account/activations",
        json={"token": activation, "password": None},
    )
    assert response.status_code == 200, response.text
    login = client.post(
        "/api/account/sessions",
        data={"username": unique_email, "password": PASSWORD},
    )
    assert login.status_code == 200, login.text
    httpx.delete(f"{MAIL_URL}/messages")
    return {
        "email": unique_email,
        "password": PASSWORD,
        "token": login.json()["access_token"],
        "headers": {"Authorization": f"Bearer {login.json()['access_token']}"},
    }


@pytest.fixture
def admin_headers(active_hacker):
    value = token(active_hacker["email"], ["admin"])
    return {"Authorization": f"Bearer {value}"}


@pytest.fixture
def volunteer_headers(active_hacker):
    value = token(active_hacker["email"], ["volunteer"])
    return {"Authorization": f"Bearer {value}"}
