import base64
import io
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
import qrcode
from jinja2 import Template
from sqlmodel import select

from app.config import AppConfig, EmailConfig, SecurityConfig
from app.core.errors import ServiceError
from sqlmodel import Session
from app.models.constants import EmailMessage, EmailSubject, EmailTemplate, TokenScope
from app.models.user import AccountUser
from app.services.tokens import create_user_access_token
from app.services.wallet import generate_google_wallet_pass

logger = logging.getLogger(__name__)


def send_email(
    template: str,
    receiver: str,
    subject: str,
    textbody: str,
    context: dict,
    attachments: list | None = None,
):
    with open(template, encoding="utf-8") as file:
        html_content = Template(file.read()).render(context)

    data = {
        "From": EmailConfig.FROM_EMAIL,
        "To": receiver,
        "Subject": subject,
        "HtmlBody": html_content,
        "TextBody": textbody,
        "MessageStream": "outbound",
    }
    if attachments:
        data["Attachments"] = []
        for content_id, file_bytes, mime_type in attachments:
            if hasattr(file_bytes, "read"):
                file_bytes = file_bytes.read()
            data["Attachments"].append(
                {
                    "Name": f"{content_id}.png",
                    "Content": base64.b64encode(file_bytes).decode("utf-8"),
                    "ContentType": mime_type,
                    "ContentID": f"cid:{content_id}",
                }
            )

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "X-Postmark-Server-Token": EmailConfig.POSTMARK_API_KEY,
    }
    timeout = httpx.Timeout(10.0, connect=5.0)
    transport = httpx.HTTPTransport(retries=2)
    with httpx.Client(timeout=timeout, transport=transport) as client:
        for attempt in range(3):
            try:
                response = client.post(
                    EmailConfig.POSTMARK_URL, json=data, headers=headers
                )
            except httpx.RequestError:
                if attempt == 2:
                    raise
                continue
            if response.status_code == 429 or response.status_code >= 500:
                if attempt < 2:
                    continue
            response.raise_for_status()
            return (response.status_code, response.json())
    raise RuntimeError("Postmark request exhausted retries")


def send_activation_email(email: str, session: Session) -> tuple[int, Any]:
    selected_user = session.exec(
        select(AccountUser).where(AccountUser.email == email)
    ).first()
    if not selected_user:
        raise ServiceError(status_code=404, detail="User does not exist")
    if selected_user.is_active:
        raise ServiceError(status_code=404, detail="User already activated")

    now = datetime.now(timezone.utc)
    cooldown = timedelta(minutes=SecurityConfig.ACTIVATION_EMAIL_COOLDOWN_MINUTES)
    if selected_user.last_activation_email_sent:
        last_sent = selected_user.last_activation_email_sent
        if last_sent.tzinfo is None:
            last_sent = last_sent.replace(tzinfo=timezone.utc)
        if now - last_sent < cooldown:
            raise ServiceError(
                status_code=429,
                detail="Activation email already sent recently. Please wait a few minutes.",
            )

    access_token = create_user_access_token(
        selected_user,
        [TokenScope.ACCOUNT_ACTIVATE.value],
        timedelta(minutes=SecurityConfig.ACTIVATION_TOKEN_EXPIRE_MINUTES),
    )
    activation_url = AppConfig.get_activation_url(access_token)
    result = send_email(
        EmailTemplate.ACTIVATION,
        email,
        EmailSubject.ACTIVATION,
        EmailMessage.activation_text(activation_url),
        {"url": activation_url},
    )
    selected_user.last_activation_email_sent = now
    session.add(selected_user)
    session.commit()
    return result


def send_activation_email_in_background(email: str) -> None:
    """Send activation mail with a fresh session after the HTTP response."""
    from app.core.db import engine

    try:
        with Session(engine) as session:
            send_activation_email(email, session)
    except ServiceError as error:
        if error.status_code != 429:
            logger.warning(
                "Activation email for %s was not sent: %s", email, error.detail
            )
    except Exception:
        logger.exception("Activation email for %s could not be sent", email)


def send_email_safely(*args, **kwargs) -> None:
    try:
        send_email(*args, **kwargs)
    except Exception:
        logger.exception("Background email could not be sent")


def send_rsvp_safely(user_email: str, user_full_name: str, application_id: str) -> None:
    try:
        send_rsvp(user_email, user_full_name, application_id)
    except Exception:
        logger.exception("RSVP for application %s could not be sent", application_id)


def create_qr_code(application_id: str):
    qr = qrcode.QRCode(
        version=3,
        box_size=5,
        border=10,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
    )
    qr.add_data(application_id)
    qr.make(fit=True)
    return qr.make_image(fill_color="black", back_color="white")


def send_rsvp(user_email: str, user_full_name: str, application_id: str):
    image_bytes = io.BytesIO()
    create_qr_code(application_id).save(image_bytes, format="PNG")
    image_bytes.seek(0)

    send_email(
        EmailTemplate.RSVP,
        user_email,
        EmailSubject.rsvp(AppConfig.EVENT_NAME),
        EmailMessage.rsvp_text(AppConfig.FRONTEND_URL),
        {
            "start_date": AppConfig.EVENT_START_DATE.strftime("%B %d %Y"),
            "end_date": AppConfig.EVENT_END_DATE.strftime("%B %d %Y"),
            "due_date": AppConfig.RSVP_DUE_DATE,
            "apple_url": AppConfig.get_apple_wallet_url(application_id),
            "google_url": AppConfig.GOOGLE_WALLET_PASS_URL
            or generate_google_wallet_pass(user_full_name, application_id),
        },
        attachments=[("qr_code", image_bytes, "image/png")],
    )
