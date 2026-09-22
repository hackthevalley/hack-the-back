import hashlib
import json
from io import BytesIO
from types import SimpleNamespace
from zipfile import ZipFile

import pytest
from PIL import Image

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
    poster = payload["posterGeneric"]
    assert poster["headerFields"][0]["value"] == "Hacker"
    assert poster["primaryFields"][0]["value"] == "User"
    assert poster["primaryFields"][1]["value"] == AppConfig.get_event_date_range()
    assert poster["footerFields"][0]["value"] == AppConfig.EVENT_LOCATION
    assert poster["backFields"][0]["value"] == AppConfig.EVENT_NAME
    assert not any(name.startswith("strip") for name in result._files)
    for asset in (
        "logo", "logo@2x", "logo@3x",
        "background", "background@2x", "background@3x",
        "artwork", "artwork@2x", "artwork@3x",
        "primaryLogo", "primaryLogo@2x", "primaryLogo@3x",
    ):
        assert result._files[f"{asset}.png"] == wallet.Path(
            f"images/apple-wallet/{asset}.png"
        ).read_bytes()


def test_poster_wallet_archive_preserves_qr_fallback_and_asset_manifest(monkeypatch):
    monkeypatch.setattr(wallet.Path, "exists", lambda _self: True)
    monkeypatch.setattr(AppConfig, "APPLE_TEAM_IDENTIFIER", "team")
    monkeypatch.setattr(AppConfig, "APPLE_PASS_TYPE_IDENTIFIER", "pass")
    monkeypatch.setattr(AppConfig, "APPLE_WALLET_KEY_PASSWORD", "password")
    # Build the real archive; only certificate signing is replaced.
    monkeypatch.setattr(
        wallet.Pass, "_createSignatureCrypto", lambda *_args: b"test-signature"
    )

    result = wallet.generate_apple_wallet_pass("Ada Lovelace", "application-id")
    with ZipFile(result) as archive:
        payload = json.loads(archive.read("pass.json"))
        assert payload["posterGeneric"]["primaryFields"][0]["value"] == "Ada Lovelace"
        assert payload["eventTicket"]["secondaryFields"][0]["value"] == "Ada Lovelace"
        assert payload["barcodes"][0]["format"] == "PKBarcodeFormatQR"
        assert payload["barcodes"][0]["message"] == "application-id"
        assert payload["barcode"]["message"] == "application-id"
        manifest = json.loads(archive.read("manifest.json"))
        assert set(manifest) == set(archive.namelist()) - {"manifest.json", "signature"}
        for name, digest in manifest.items():
            assert hashlib.sha1(archive.read(name)).hexdigest() == digest
        for scale in (1, 2, 3):
            suffix = "" if scale == 1 else f"@{scale}x"
            with Image.open(BytesIO(archive.read(f"artwork{suffix}.png"))) as artwork:
                assert artwork.size == (358 * scale, 448 * scale)
                assert artwork.convert("RGB").getpixel((0, artwork.height - 1)) == (120, 57, 220)
            with Image.open(BytesIO(archive.read(f"primaryLogo{suffix}.png"))) as logo:
                assert logo.size == (30 * scale, 30 * scale)
                assert logo.mode == "RGBA"
                assert all(
                    (r, g, b) == (255, 255, 255)
                    for r, g, b, alpha in logo.get_flattened_data()
                    if alpha
                )


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
