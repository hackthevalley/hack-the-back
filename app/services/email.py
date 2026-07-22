import base64
import io
from datetime import datetime, timedelta, timezone

import httpx
import qrcode
from fastapi import HTTPException, status
from jinja2 import Template
from sqlmodel import select

from app.config import AppConfig, EmailConfig, SecurityConfig
from app.core.db import SessionDep
from app.models.constants import EmailMessage, EmailSubject, EmailTemplate, TokenScope
from app.models.user import Account_User
from app.services.auth import create_access_token
from app.services.wallet import generate_google_wallet_pass


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
    with httpx.Client() as client:
        response = client.post(EmailConfig.POSTMARK_URL, json=data, headers=headers)
    return (response.status_code, response.json())


def send_activation_email(email: str, session: SessionDep):
    selected_user = session.exec(
        select(Account_User).where(Account_User.email == email)
    ).first()
    if not selected_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User does not exist"
        )
    if selected_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User already activated"
        )

    now = datetime.now(timezone.utc)
    cooldown = timedelta(minutes=SecurityConfig.ACTIVATION_EMAIL_COOLDOWN_MINUTES)
    if selected_user.last_activation_email_sent:
        last_sent = selected_user.last_activation_email_sent
        if last_sent.tzinfo is None:
            last_sent = last_sent.replace(tzinfo=timezone.utc)
        if now - last_sent < cooldown:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Activation email already sent recently. Please wait a few minutes.",
            )

    selected_user.last_activation_email_sent = now
    session.add(selected_user)
    session.commit()
    access_token = create_access_token(
        data={
            "sub": str(selected_user.email),
            "fullName": selected_user.full_name,
            "firstName": selected_user.first_name,
            "lastName": selected_user.last_name,
            "scopes": [TokenScope.ACCOUNT_ACTIVATE.value],
        },
        secret_key=SecurityConfig.SECRET_KEY,
        algorithm=SecurityConfig.ALGORITHM,
        expires_delta=timedelta(
            minutes=SecurityConfig.ACTIVATION_TOKEN_EXPIRE_MINUTES
        ),
    )
    activation_url = AppConfig.get_activation_url(access_token)
    return send_email(
        EmailTemplate.ACTIVATION,
        email,
        EmailSubject.ACTIVATION,
        EmailMessage.activation_text(activation_url),
        {"url": access_token},
    )


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
