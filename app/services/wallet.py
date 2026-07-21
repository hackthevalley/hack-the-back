from pathlib import Path

import google.auth.jwt
from google.oauth2 import service_account
from py_pkpass.models import Barcode, BarcodeFormat, EventTicket, Pass

from app.config import AppConfig


def generate_apple_wallet_pass(user_name: str, application_id: str):
    required_files = {
        "icon": "images/icon-29x29.png",
        "logo": "images/logo-50x50.png",
        "cert": "certs/apple/cert.pem",
        "key": "certs/apple/key.pem",
        "wwdr": "certs/apple/wwdr.pem",
    }

    missing_files = [
        f"{file_type}: {file_path}"
        for file_type, file_path in required_files.items()
        if not Path(file_path).exists()
    ]
    if missing_files:
        raise FileNotFoundError(
            f"Missing required files for Apple Wallet pass generation: {', '.join(missing_files)}"
        )

    if not AppConfig.APPLE_TEAM_IDENTIFIER:
        raise RuntimeError("APPLE_TEAM_IDENTIFIER not configured")
    if not AppConfig.APPLE_PASS_TYPE_IDENTIFIER:
        raise RuntimeError("APPLE_PASS_TYPE_IDENTIFIER not configured")
    if not AppConfig.APPLE_WALLET_KEY_PASSWORD:
        raise RuntimeError("APPLE_WALLET_KEY_PASSWORD not configured")

    card_info = EventTicket()
    card_info.addPrimaryField("role", "Hacker", "Role")
    card_info.addSecondaryField("name", user_name, "Name")
    card_info.addSecondaryField("date", AppConfig.get_event_date_range(), "Date")
    card_info.addAuxiliaryField("location", AppConfig.EVENT_LOCATION, "Location")

    apple_pass = Pass(
        card_info,
        teamIdentifier=AppConfig.APPLE_TEAM_IDENTIFIER,
        passTypeIdentifier=AppConfig.APPLE_PASS_TYPE_IDENTIFIER,
        organizationName="Hack the Valley",
    )
    apple_pass.serialNumber = application_id
    apple_pass.description = f"{AppConfig.EVENT_NAME} hacker pass"
    apple_pass.logoText = AppConfig.EVENT_NAME
    apple_pass.backgroundColor = "rgb(25, 24, 32)"
    apple_pass.foregroundColor = "rgb(255,255,255)"
    apple_pass.labelColor = "rgb(255, 255, 255)"
    apple_pass.barcode = Barcode(application_id, format=BarcodeFormat.QR)

    with open(required_files["icon"], "rb") as icon_file:
        apple_pass.addFile("icon.png", icon_file)
    with open(required_files["logo"], "rb") as logo_file:
        apple_pass.addFile("logo.png", logo_file)

    return apple_pass.create(
        required_files["cert"],
        required_files["key"],
        required_files["wwdr"],
        AppConfig.APPLE_WALLET_KEY_PASSWORD,
        None,
    )


def generate_google_wallet_pass(user_name: str, application_id: str):
    credentials_file = Path("certs/google/credentials.json")
    if not credentials_file.exists():
        raise FileNotFoundError(
            f"Google Wallet credentials file not found: {credentials_file}"
        )
    if not AppConfig.GOOGLE_WALLET_ISSUER_ID:
        raise RuntimeError("GOOGLE_WALLET_ISSUER_ID not configured")
    if not AppConfig.GOOGLE_WALLET_CLASS_ID:
        raise RuntimeError("GOOGLE_WALLET_CLASS_ID not configured")

    credentials = service_account.Credentials.from_service_account_file(
        credentials_file,
        scopes=["https://www.googleapis.com/auth/wallet_object.issuer"],
    )
    issuer_id = AppConfig.GOOGLE_WALLET_ISSUER_ID
    payload = {
        "iss": credentials.service_account_email,
        "aud": "google",
        "typ": "savetowallet",
        "origins": [],
        "payload": {
            "eventTicketObjects": [
                {
                    "id": f"{issuer_id}.{application_id}",
                    "classId": f"{issuer_id}.{AppConfig.GOOGLE_WALLET_CLASS_ID}",
                    "ticketHolderName": user_name,
                    "state": "ACTIVE",
                    "barcode": {
                        "type": "QR_CODE",
                        "value": application_id,
                        "alternateText": "Present when signing in/getting food!",
                    },
                    "eventId": "hackthevalleyx",
                    "venue": {"name": AppConfig.EVENT_LOCATION},
                    "textModulesData": [{"header": "Name", "body": user_name}],
                }
            ]
        },
    }
    token = google.auth.jwt.encode(credentials.signer, payload).decode("utf-8")
    return f"https://pay.google.com/gp/v/save/{token}"
