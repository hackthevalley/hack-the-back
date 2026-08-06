from importlib import import_module

account = import_module("app.routers.admin.account")
bulk_email = import_module("app.services.bulk_email")


def test_filename_sanitization():
    assert account._sanitize_filename("../../bad<script>.pdf") == "badscript.pdf"
    assert account._sanitize_filename("...") == "file.pdf"
    assert len(account._sanitize_filename("a" * 300 + ".pdf")) == 255
    assert len(account._sanitize_filename("a" * 300)) == 255


def test_batch_email_success_failure_and_exception(monkeypatch):
    responses = iter([(200, {"ok": True}), (500, {"ok": False})])

    def fake_send(*_args, **_kwargs):
        return next(responses)

    monkeypatch.setattr(bulk_email, "send_email", fake_send)
    bulk_email.send_batch_email(
        [{"email": "ok@example.com"}, {"email": "bad@example.com"}],
        "template",
        "subject",
        "body",
        None,
    )

    def exploding(*_args, **_kwargs):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(bulk_email, "send_email", exploding)
    bulk_email.send_batch_email(
        [{}], "template", "subject", "body", {"shared": True}
    )
