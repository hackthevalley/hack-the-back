from google.auth import jwt
from google.oauth2.service_account import Credentials

from hacktheback import settings


def generate_google_wallet_link(hacker_id, email):
    google_credentials = Credentials.from_service_account_file(
        settings.GOOGLE_WALLET_API_CREDENTIALS,
        scopes=['https://www.googleapis.com/auth/wallet_object.issuer']
    )
    issuer_id = settings.GOOGLE_WALLET_ISSUER_ID
    object_id = f"{issuer_id}.{hacker_id}"
    class_id = f"{issuer_id}.{settings.GOOGLE_WALLET_CLASS_ID}"
    event_ticket_object = {
        "id": object_id,
        "classId": class_id,
        "ticketHolderName": email,
        "state": "ACTIVE",
        "barcode": {
            "type": "QR_CODE",
            "value": hacker_id,
            "alternateText": "Present when signing in/getting food!",
        }
    }

    claims = {
        "iss": google_credentials.service_account_email,
        "aud": "google",
        "origins": [],
        "typ": "savetowallet",
        "payload": {
            "eventTicketObjects": [
                event_ticket_object
            ]
        }
    }

    token = jwt.encode(google_credentials.signer, claims).decode('utf-8')
    return settings.GOOGLE_WALLET_API_URL_FORMAT.format(token=token)
