from types import SimpleNamespace

from jinja2 import Template

from app.config import AppConfig
from app.services import email as email_service


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
        "create_access_token",
        lambda **_kwargs: "example-token",
    )
    monkeypatch.setattr(email_service, "send_email", fake_send_email)
    monkeypatch.setattr(AppConfig, "FRONTEND_URL", "http://localhost:3000")

    email_service.send_activation_email(user.email, Session())

    activation_url = "http://localhost:3000/activate?token=example-token"
    assert sent["context"] == {"url": activation_url}
    assert activation_url in sent["textbody"]
