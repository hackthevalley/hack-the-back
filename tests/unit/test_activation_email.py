from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from jinja2 import Template

from app.config import AppConfig
from app.core.errors import ServiceError
from app.services import email as email_service


EMAIL_TEMPLATES = ("activation.html", "confirmation.html", "password_reset.html")


def test_activation_url_uses_configured_frontend(monkeypatch):
    monkeypatch.setattr(AppConfig, "FRONTEND_URL", "http://localhost:3000")

    assert (
        AppConfig.get_activation_url("example-token")
        == "http://localhost:3000/activate?token=example-token"
    )


def test_activation_template_uses_complete_url():
    activation_url = "https://example.com/activate?token=example-token"
    with open("templates/activation.html", encoding="utf-8") as template_file:
        rendered = Template(template_file.read()).render(url=activation_url)

    assert f'href="{activation_url}"' in rendered
    assert f">{activation_url}</a" in rendered


def test_email_footers_use_table_aligned_current_logo():
    for template_name in EMAIL_TEMPLATES:
        template = (Path("templates") / template_name).read_text(encoding="utf-8")

        assert (
            'src="https://raw.githubusercontent.com/hackthevalley/internal-resources/main/functions/static/htvlogo.png"'
            in template
        )
        assert 'colspan="3" align="right" valign="bottom"' in template
        assert "position: absolute; bottom: 0; right: 0" not in template


def test_activation_email_passes_complete_url(monkeypatch):
    user = SimpleNamespace(
        email="hacker@example.com",
        first_name="Hack",
        last_name="Er",
        full_name="Hack Er",
        is_active=False,
        last_activation_email_sent=None,
        token_version=0,
    )

    class Result:
        def first(self):
            return user

    class Session:
        def exec(self, _statement):
            return Result()

        def add(self, _user):
            pass

        def commit(self):
            pass

    sent = {}

    def fake_send_email(template, receiver, subject, textbody, context):
        sent.update(
            template=template,
            receiver=receiver,
            subject=subject,
            textbody=textbody,
            context=context,
        )
        return 200, {}

    monkeypatch.setattr(
        email_service,
        "create_user_access_token",
        lambda *_args, **_kwargs: "example-token",
    )
    monkeypatch.setattr(email_service, "send_email", fake_send_email)
    monkeypatch.setattr(AppConfig, "FRONTEND_URL", "http://localhost:3000")

    email_service.send_activation_email(user.email, Session())

    activation_url = "http://localhost:3000/activate?token=example-token"
    assert sent["context"] == {"url": activation_url}
    assert activation_url in sent["textbody"]


def test_activation_email_failure_does_not_start_cooldown(monkeypatch):
    user = SimpleNamespace(
        email="hacker@example.com",
        first_name="Hack",
        last_name="Er",
        full_name="Hack Er",
        is_active=False,
        last_activation_email_sent=None,
        token_version=0,
    )

    class Result:
        def first(self):
            return user

    class Session:
        commits = 0

        def exec(self, _statement):
            return Result()

        def add(self, _user):
            pass

        def commit(self):
            self.commits += 1

    session = Session()
    monkeypatch.setattr(
        email_service,
        "create_user_access_token",
        lambda *_args, **_kwargs: "example-token",
    )

    def fail_to_send(*_args, **_kwargs):
        raise RuntimeError("Postmark unavailable")

    monkeypatch.setattr(email_service, "send_email", fail_to_send)

    try:
        email_service.send_activation_email(user.email, session)
    except RuntimeError:
        pass
    else:
        raise AssertionError("Expected the email failure to propagate")

    assert user.last_activation_email_sent is None
    assert session.commits == 0


def test_send_email_retries_transient_statuses(monkeypatch, tmp_path):
    template = tmp_path / "email.html"
    template.write_text("Hello {{ name }}", encoding="utf-8")
    responses = [
        httpx.Response(500, request=httpx.Request("POST", "https://postmark.test")),
        httpx.Response(429, request=httpx.Request("POST", "https://postmark.test")),
        httpx.Response(
            200,
            json={"Message": "OK"},
            request=httpx.Request("POST", "https://postmark.test"),
        ),
    ]

    class Client:
        def __init__(self, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            pass

        def post(self, *_args, **_kwargs):
            return responses.pop(0)

    monkeypatch.setattr(email_service.httpx, "Client", Client)

    status_code, body = email_service.send_email(
        str(template),
        "hacker@example.com",
        "Subject",
        "Text",
        {"name": "Hacker"},
    )

    assert status_code == 200
    assert body == {"Message": "OK"}
    assert responses == []


def test_send_email_retries_request_errors_then_raises(monkeypatch, tmp_path):
    template = tmp_path / "email.html"
    template.write_text("Hello", encoding="utf-8")
    attempts = 0

    class Client:
        def __init__(self, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            pass

        def post(self, *_args, **_kwargs):
            nonlocal attempts
            attempts += 1
            raise httpx.ConnectError("offline")

    monkeypatch.setattr(email_service.httpx, "Client", Client)

    with pytest.raises(httpx.ConnectError):
        email_service.send_email(
            str(template), "hacker@example.com", "Subject", "Text", {}
        )
    assert attempts == 3


def test_background_email_helpers_contain_failures(monkeypatch):
    def fail(*_args, **_kwargs):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(email_service, "send_email", fail)
    monkeypatch.setattr(email_service, "send_rsvp", fail)

    assert email_service.send_email_safely("template", "receiver") is None
    assert email_service.send_rsvp_safely("email", "name", "application") is None


def test_background_activation_uses_fresh_session(monkeypatch):
    calls = []

    class Session:
        def __init__(self, engine):
            calls.append(("session", engine))

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            pass

    monkeypatch.setattr(email_service, "Session", Session)
    monkeypatch.setattr(
        email_service,
        "send_activation_email",
        lambda email, session: calls.append((email, session)),
    )

    email_service.send_activation_email_in_background("hacker@example.com")

    assert calls[1][0] == "hacker@example.com"


@pytest.mark.parametrize(
    "error",
    [
        ServiceError(status_code=429, detail="cooldown"),
        ServiceError(status_code=503, detail="provider unavailable"),
        RuntimeError("unexpected"),
    ],
)
def test_background_activation_contains_failures(monkeypatch, error):
    class Session:
        def __init__(self, _engine):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            pass

    monkeypatch.setattr(email_service, "Session", Session)
    monkeypatch.setattr(
        email_service,
        "send_activation_email",
        lambda *_args: (_ for _ in ()).throw(error),
    )

    assert (
        email_service.send_activation_email_in_background("hacker@example.com") is None
    )
