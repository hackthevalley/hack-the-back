from types import SimpleNamespace

import pytest

from app.config import AppConfig
from app.services import wallet


def test_wallet_missing_files(monkeypatch):
    monkeypatch.setattr(wallet.Path, "exists", lambda _self: False)
    with pytest.raises(FileNotFoundError, match="Missing required files"):
        wallet.generate_apple_wallet_pass("User", "app-id")
    with pytest.raises(FileNotFoundError, match="credentials file"):
        wallet.generate_google_wallet_pass("User", "app-id")


@pytest.mark.parametrize(
    "setting",
    [
        "APPLE_TEAM_IDENTIFIER",
        "APPLE_PASS_TYPE_IDENTIFIER",
        "APPLE_WALLET_KEY_PASSWORD",
    ],
)
def test_apple_wallet_required_configuration(monkeypatch, setting):
    monkeypatch.setattr(wallet.Path, "exists", lambda _self: True)
    monkeypatch.setattr(AppConfig, "APPLE_TEAM_IDENTIFIER", "team")
    monkeypatch.setattr(AppConfig, "APPLE_PASS_TYPE_IDENTIFIER", "pass")
    monkeypatch.setattr(AppConfig, "APPLE_WALLET_KEY_PASSWORD", "password")
    monkeypatch.setattr(AppConfig, setting, None)
    with pytest.raises(RuntimeError):
        wallet.generate_apple_wallet_pass("User", "app-id")


def test_apple_wallet_branding_and_check_in_details(monkeypatch):
    monkeypatch.setattr(wallet.Path, "exists", lambda _self: True)
    monkeypatch.setattr(AppConfig, "APPLE_TEAM_IDENTIFIER", "team")
    monkeypatch.setattr(AppConfig, "APPLE_PASS_TYPE_IDENTIFIER", "pass")
    monkeypatch.setattr(AppConfig, "APPLE_WALLET_KEY_PASSWORD", "password")
    # Exercise real serialization and asset loading without signing credentials.
    monkeypatch.setattr(wallet.Pass, "create", lambda self, *_args: self)

    result = wallet.generate_apple_wallet_pass("User", "app-id")
    payload = result.json_dict()
    assert payload["backgroundColor"] == "rgb(120, 57, 220)"
    assert payload["labelColor"] == "rgb(230, 224, 241)"
    assert payload["serialNumber"] == "app-id"
    assert payload["barcodes"][0]["message"] == "app-id"
    ticket = payload["eventTicket"]
    assert ticket["headerFields"][0]["value"] == "Hacker"
    assert not ticket.get("primaryFields")
    assert ticket["secondaryFields"][0]["value"] == "User"
    assert ticket["secondaryFields"][1]["value"] == AppConfig.get_event_date_range()
    assert ticket["auxiliaryFields"][0]["value"] == AppConfig.EVENT_LOCATION
    assert result._files["strip.png"] == wallet.Path("images/wallet-banner.png").read_bytes()


def test_google_wallet_required_configuration_and_success(monkeypatch):
    monkeypatch.setattr(wallet.Path, "exists", lambda _self: True)
    monkeypatch.setattr(AppConfig, "GOOGLE_WALLET_ISSUER_ID", None)
    with pytest.raises(RuntimeError, match="ISSUER"):
        wallet.generate_google_wallet_pass("User", "app-id")

    monkeypatch.setattr(AppConfig, "GOOGLE_WALLET_ISSUER_ID", "issuer")
    monkeypatch.setattr(AppConfig, "GOOGLE_WALLET_CLASS_ID", None)
    with pytest.raises(RuntimeError, match="CLASS"):
        wallet.generate_google_wallet_pass("User", "app-id")

    credentials = SimpleNamespace(
        service_account_email="e2e@example.com", signer=object()
    )
    monkeypatch.setattr(AppConfig, "GOOGLE_WALLET_CLASS_ID", "class")
    monkeypatch.setattr(
        wallet.service_account.Credentials,
        "from_service_account_file",
        lambda *_args, **_kwargs: credentials,
    )
    captured = {}

    def encode(_signer, payload):
        captured.update(payload)
        return b"signed"

    monkeypatch.setattr(wallet.google.auth.jwt, "encode", encode)
    result = wallet.generate_google_wallet_pass("User", "app-id")
    assert result == "https://pay.google.com/gp/v/save/signed"
    ticket = captured["payload"]["eventTicketObjects"][0]
    assert ticket["hexBackgroundColor"] == "#7839DC"
    assert ticket["heroImage"]["sourceUri"]["uri"] == wallet.WALLET_BANNER_URL
    assert ticket["id"] == "issuer.app-id"
    assert ticket["classId"] == "issuer.class"
    assert ticket["ticketHolderName"] == "User"
    assert ticket["barcode"]["value"] == "app-id"
