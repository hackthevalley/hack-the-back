import base64
from datetime import datetime, timedelta, timezone
from typing import Annotated

import aiofiles
import google.auth.jwt
import httpx
import jwt
import qrcode
from applepassgenerator.client import ApplePassGeneratorClient
from applepassgenerator.models import Barcode, BarcodeFormat, EventTicket
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from google.oauth2 import service_account
from jinja2 import Template
from jwt.exceptions import InvalidTokenError
from sqlalchemy.orm import selectinload
from sqlmodel import select

from app.config import AppConfig, EmailConfig, SecurityConfig
from app.core.db import SessionDep
from app.models.constants import (
    EmailMessage,
    EmailSubject,
    EmailTemplate,
    QuestionLabel,
    TokenScope,
)
from app.models.forms import (
    Forms_Answer,
    Forms_AnswerFile,
    Forms_Application,
    Forms_Form,
    Forms_HackathonApplicant,
    Forms_Question,
    StatusEnum,
)
from app.models.token import TokenData
from app.models.user import Account_User

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="login",
    scopes={
        TokenScope.ADMIN.value: "Allow user to call admin routes",
        TokenScope.VOLUNTEER.value: "Allow user to call qr routes",
    },
)

credentials_exception = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid credentials or expired token",
    headers={"WWW-Authenticate": "Bearer"},
)


async def decode_jwt(token: Annotated[str, Depends(oauth2_scheme)]):
    try:
        payload = jwt.decode(
            token, SecurityConfig.SECRET_KEY, algorithms=[SecurityConfig.ALGORITHM]
        )
        email: str = payload.get("sub")
        scopes: list[str] = payload.get("scopes", [])
        fullName: str = payload.get("fullName")
        firstName: str = payload.get("firstName")
        lastName: str = payload.get("lastName")
        if email is None:
            raise credentials_exception
        token_data = TokenData(
            email=email,
            fullName=fullName,
            firstName=firstName,
            lastName=lastName,
            scopes=scopes,
        )
    except InvalidTokenError:
        raise credentials_exception
    return token_data


async def get_current_user(
    token_data: Annotated[TokenData, Depends(decode_jwt)], session: SessionDep
) -> Account_User:
    if (
        TokenScope.RESET_PASSWORD.value in token_data.scopes
        or TokenScope.ACCOUNT_ACTIVATE.value in token_data.scopes
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Weak token")

    statement = (
        select(Account_User)
        .where(Account_User.email == token_data.email)
        .options(selectinload(Account_User.application))
    )
    user = session.exec(statement).first()

    if user is None:
        raise credentials_exception
    return user


def create_access_token(
    data: dict, SECRET_KEY: str, ALGORITHM: str, expires_delta: timedelta | None = None
):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=1)
    to_encode.update({"iat": datetime.now(timezone.utc), "exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def createapplication(
    current_user: Account_User,
    session: SessionDep,
) -> Forms_Application:
    if not all([current_user.first_name, current_user.last_name, current_user.email]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User profile incomplete - missing first name, last name, or email",
        )
    if not all(
        [
            current_user.first_name.strip(),
            current_user.last_name.strip(),
            current_user.email.strip(),
        ]
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User profile incomplete - first name, last name, or email cannot be empty",
        )

    questions = session.exec(
        select(Forms_Question).order_by(Forms_Question.question_order)
    ).all()

    application = Forms_Application(
        user=current_user,
        is_draft=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    session.add(application)
    session.flush()

    hackathon_applicant = Forms_HackathonApplicant(
        applicant=application,
        status=StatusEnum.APPLYING,
    )
    session.add(hackathon_applicant)

    answers = []
    resume_question = None
    for q in questions:
        if not QuestionLabel.contains_resume(q.label):
            answer_value = None
            label_lower = q.label.lower().strip()
            if label_lower == QuestionLabel.FIRST_NAME.value.lower():
                answer_value = current_user.first_name
            elif label_lower == QuestionLabel.LAST_NAME.value.lower():
                answer_value = current_user.last_name
            elif label_lower == QuestionLabel.EMAIL.value.lower():
                answer_value = current_user.email

            answers.append(
                Forms_Answer(
                    application_id=application.application_id,
                    question_id=q.question_id,
                    answer=answer_value,
                )
            )
        else:
            resume_question = q

    session.add_all(answers)

    if resume_question:
        resume_answer = Forms_AnswerFile(
            application_id=application.application_id,
            original_filename=None,
            file_path=None,
            question_id=resume_question.question_id,
        )
        session.add(resume_answer)

    session.commit()

    session.refresh(current_user)

    statement = (
        select(Forms_Application)
        .where(Forms_Application.uid == current_user.uid)
        .options(
            selectinload(Forms_Application.form_answers),
            selectinload(Forms_Application.form_answersfile),
            selectinload(Forms_Application.hackathonapplicant),
        )
    )
    return session.exec(statement).first()


async def isValidSubmissionTime(session: SessionDep, user: Account_User = None):
    """
    Check if it's valid time to submit application.
    Walk-in users (with WALK_IN or WALK_IN_SUBMITTED status) can always submit.
    """
    if user and user.application and user.application.hackathonapplicant:
        status = user.application.hackathonapplicant.status
        if status in [StatusEnum.WALK_IN, StatusEnum.WALK_IN_SUBMITTED]:
            return True

    time = session.exec(select(Forms_Form).limit(1)).first()
    if time is None:
        return False
    return time.start_at < datetime.now(timezone.utc) < time.end_at


async def sendEmail(
    template: str,
    receiver: str,
    subject: str,
    textbody: str,
    context: str,
    attachments: list = None,
):
    async with aiofiles.open(template, "r", encoding="utf-8") as file:
        raw_html = await file.read()
    html_template = Template(raw_html)
    html_content = html_template.render(context)
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "X-Postmark-Server-Token": EmailConfig.POSTMARK_API_KEY,
    }
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
        for cid, file_bytes, mime_type in attachments:
            if hasattr(file_bytes, "read"):
                file_bytes = file_bytes.read()
            encoded = base64.b64encode(file_bytes).decode("utf-8")
            data["Attachments"].append(
                {
                    "Name": f"{cid}.png",
                    "Content": encoded,
                    "ContentType": mime_type,
                    "ContentID": f"cid:{cid}",
                }
            )
    async with httpx.AsyncClient() as client:
        response = await client.post(
            EmailConfig.POSTMARK_URL, json=data, headers=headers
        )
    return (response.status_code, response.json())


async def sendActivate(email: str, session: SessionDep):
    statement = select(Account_User).where(Account_User.email == email)
    selected_user = session.exec(statement).first()
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
                status_code=429,
                detail="Activation email already sent recently. Please wait a few minutes.",
            )

    selected_user.last_activation_email_sent = now
    session.add(selected_user)
    session.commit()
    scopes = []
    scopes.append(TokenScope.ACCOUNT_ACTIVATE.value)
    access_token_expires = timedelta(
        minutes=SecurityConfig.ACTIVATION_TOKEN_EXPIRE_MINUTES
    )
    access_token = create_access_token(
        data={
            "sub": str(selected_user.email),
            "fullName": selected_user.full_name,
            "firstName": selected_user.first_name,
            "lastName": selected_user.last_name,
            "scopes": scopes,
        },
        SECRET_KEY=SecurityConfig.SECRET_KEY,
        ALGORITHM=SecurityConfig.ALGORITHM,
        expires_delta=access_token_expires,
    )
    activation_url = AppConfig.get_activation_url(access_token)
    response = await sendEmail(
        EmailTemplate.ACTIVATION,
        email,
        EmailSubject.ACTIVATION,
        EmailMessage.activation_text(activation_url),
        {"url": access_token},
    )
    return response


async def createQRCode(application_id: str):
    qr = qrcode.QRCode(
        version=3,
        box_size=5,
        border=10,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
    )
    qr.add_data(application_id)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    return img


def generate_apple_wallet_pass(user_name: str, application_id: str):
    """
    Generate an Apple Wallet pass for a hacker.

    Args:
        user_name: Full name of the user
        application_id: Application UUID

    Returns:
        Binary pkpass file

    Raises:
        FileNotFoundError: If required image or certificate files are missing
        RuntimeError: If wallet configuration is incomplete
    """
    from pathlib import Path

    required_files = {
        "icon": "images/icon-29x29.png",
        "logo": "images/logo-50x50.png",
        "cert": "certs/apple/cert.pem",
        "key": "certs/apple/key.pem",
        "wwdr": "certs/apple/wwdr.pem",
    }

    missing_files = []
    for file_type, file_path in required_files.items():
        if not Path(file_path).exists():
            missing_files.append(f"{file_type}: {file_path}")

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

    date_range_str = AppConfig.get_event_date_range()
    card_info = EventTicket()
    card_info.add_primary_field("role", "Hacker", "Role")
    card_info.add_secondary_field("name", user_name, "Name")
    card_info.add_secondary_field("date", date_range_str, "Date")
    card_info.add_auxiliary_field("location", AppConfig.EVENT_LOCATION, "Location")

    client = ApplePassGeneratorClient(
        team_identifier=AppConfig.APPLE_TEAM_IDENTIFIER,
        pass_type_identifier=AppConfig.APPLE_PASS_TYPE_IDENTIFIER,
        organization_name="Hack the Valley",
    )
    apple_pass = client.get_pass(card_info)
    apple_pass.logo_text = AppConfig.EVENT_NAME
    apple_pass.background_color = "rgb(25, 24, 32)"
    apple_pass.foreground_color = "rgb(255,255,255)"
    apple_pass.label_color = "rgb(255, 255, 255)"
    apple_pass.barcode = Barcode(application_id, format=BarcodeFormat.QR)

    with open(required_files["icon"], "rb") as icon_file:
        apple_pass.add_file("icon.png", icon_file)
    with open(required_files["logo"], "rb") as logo_file:
        apple_pass.add_file("logo.png", logo_file)

    package = apple_pass.create(
        required_files["cert"],
        required_files["key"],
        required_files["wwdr"],
        AppConfig.APPLE_WALLET_KEY_PASSWORD,
        None,
    )

    return package


def generate_google_wallet_pass(user_name: str, application_id: str):
    """
    Generate a Google Wallet pass URL for a hacker.

    Args:
        user_name: Full name of the user
        application_id: Application UUID

    Returns:
        Google Wallet pass URL

    Raises:
        FileNotFoundError: If credentials file is missing
        RuntimeError: If wallet configuration is incomplete
    """
    from pathlib import Path

    GOOGLE_CREDENTIALS_FILE = "certs/google/credentials.json"

    if not Path(GOOGLE_CREDENTIALS_FILE).exists():
        raise FileNotFoundError(
            f"Google Wallet credentials file not found: {GOOGLE_CREDENTIALS_FILE}"
        )

    if not AppConfig.GOOGLE_WALLET_ISSUER_ID:
        raise RuntimeError("GOOGLE_WALLET_ISSUER_ID not configured")
    if not AppConfig.GOOGLE_WALLET_CLASS_ID:
        raise RuntimeError("GOOGLE_WALLET_CLASS_ID not configured")

    creds = service_account.Credentials.from_service_account_file(
        GOOGLE_CREDENTIALS_FILE,
        scopes=["https://www.googleapis.com/auth/wallet_object.issuer"],
    )

    issuer_id = AppConfig.GOOGLE_WALLET_ISSUER_ID

    class_id = f"{issuer_id}.{AppConfig.GOOGLE_WALLET_CLASS_ID}"
    object_id = f"{issuer_id}.{application_id}"

    payload = {
        "iss": creds.service_account_email,
        "aud": "google",
        "typ": "savetowallet",
        "origins": [],
        "payload": {
            "eventTicketObjects": [
                {
                    "id": object_id,
                    "classId": class_id,
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

    token_bytes = google.auth.jwt.encode(creds.signer, payload)
    token = token_bytes.decode("utf-8")
    save_url = f"https://pay.google.com/gp/v/save/{token}"
    return save_url


async def send_rsvp(user_email: str, user_full_name: str, application_id: str):
    """
    Send acceptance/RSVP email with QR code attachment and wallet passes.

    This consolidates duplicate logic for sending acceptance emails with QR codes.
    Used when accepting applications or for walk-in submissions.

    Args:
        user_email: Email address of the recipient
        user_full_name: Full name of the user for wallet passes
        application_id: Application ID for QR code generation
    """
    import io

    img = await createQRCode(application_id)
    img_bytes = io.BytesIO()
    img.save(img_bytes, format="PNG")
    img_bytes.seek(0)

    google_link = generate_google_wallet_pass(user_full_name, application_id)

    start_date_str = AppConfig.EVENT_START_DATE.strftime("%B %d %Y")
    end_date_str = AppConfig.EVENT_END_DATE.strftime("%B %d %Y")

    await sendEmail(
        EmailTemplate.RSVP,
        user_email,
        EmailSubject.rsvp(AppConfig.EVENT_NAME),
        EmailMessage.rsvp_text(AppConfig.FRONTEND_URL),
        {
            "start_date": start_date_str,
            "end_date": end_date_str,
            "due_date": AppConfig.RSVP_DUE_DATE,
            "apple_url": AppConfig.get_apple_wallet_url(application_id),
            "google_url": google_link,
        },
        attachments=[("qr_code", img_bytes, "image/png")],
    )
