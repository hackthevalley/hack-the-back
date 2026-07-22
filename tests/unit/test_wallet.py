from io import BytesIO
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
    ["APPLE_TEAM_IDENTIFIER", "APPLE_PASS_TYPE_IDENTIFIER", "APPLE_WALLET_KEY_PASSWORD"],
)
def test_apple_wallet_required_configuration(monkeypatch, setting):
    monkeypatch.setattr(wallet.Path, "exists", lambda _self: True)
    monkeypatch.setattr(AppConfig, "APPLE_TEAM_IDENTIFIER", "team")
    monkeypatch.setattr(AppConfig, "APPLE_PASS_TYPE_IDENTIFIER", "pass")
    monkeypatch.setattr(AppConfig, "APPLE_WALLET_KEY_PASSWORD", "password")
    monkeypatch.setattr(AppConfig, setting, None)
    with pytest.raises(RuntimeError):
        wallet.generate_apple_wallet_pass("User", "app-id")


def test_google_wallet_required_configuration_and_success(monkeypatch):
    monkeypatch.setattr(wallet.Path, "exists", lambda _self: True)
    monkeypatch.setattr(AppConfig, "GOOGLE_WALLET_ISSUER_ID", None)
    with pytest.raises(RuntimeError, match="ISSUER"):
        wallet.generate_google_wallet_pass("User", "app-id")

    monkeypatch.setattr(AppConfig, "GOOGLE_WALLET_ISSUER_ID", "issuer")
    monkeypatch.setattr(AppConfig, "GOOGLE_WALLET_CLASS_ID", None)
    with pytest.raises(RuntimeError, match="CLASS"):
        wallet.generate_google_wallet_pass("User", "app-id")

    credentials = SimpleNamespace(service_account_email="e2e@example.com", signer=object())
    monkeypatch.setattr(AppConfig, "GOOGLE_WALLET_CLASS_ID", "class")
    monkeypatch.setattr(
        wallet.service_account.Credentials,
        "from_service_account_file",
        lambda *_args, **_kwargs: credentials,
    )
    monkeypatch.setattr(wallet.google.auth.jwt, "encode", lambda *_args: b"signed")
    result = wallet.generate_google_wallet_pass("User", "app-id")
    assert result == "https://pay.google.com/gp/v/save/signed"
