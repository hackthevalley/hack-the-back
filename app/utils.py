import base64
import os
from datetime import date, datetime, timedelta, timezone
from typing import Annotated

import google.auth.jwt
import jwt
import qrcode
import requests
from applepassgenerator.client import ApplePassGeneratorClient
from applepassgenerator.models import Barcode, BarcodeFormat, EventTicket
from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from google.oauth2 import service_account
from jinja2 import Template
from jwt.exceptions import InvalidTokenError
from sqlalchemy.orm import selectinload
from sqlmodel import select

from app.core.db import SessionDep
from app.models.constants import TokenScope
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

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")
POSTMARK_API_KEY = os.getenv("POSTMARK_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 1

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
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
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

    # Optimize: Use eager loading to fetch user with application relationship
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

    # Preload all form questions first
    questions = session.exec(
        select(Forms_Question).order_by(Forms_Question.question_order)
    ).all()

    # Create application object
    application = Forms_Application(
        user=current_user,
        is_draft=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    session.add(application)
    session.flush()  # Flush to get application_id without committing

    # Create hackathon applicant entry
    hackathon_applicant = Forms_HackathonApplicant(
        applicant=application,
        status=StatusEnum.APPLYING,
    )
    session.add(hackathon_applicant)

    # Prepare answers
    answers = []
    resume_question = None
    for q in questions:
        if "resume" not in q.label.lower():
            answer_value = None
            label_lower = q.label.lower().strip()
            if label_lower == "first name":
                answer_value = current_user.first_name
            elif label_lower == "last name":
                answer_value = current_user.last_name
            elif label_lower == "email":
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

    # Single commit for all operations - more efficient
    session.commit()

    # REFRESH current_user (to reflect .application relationship)
    session.refresh(current_user)

    # REFRESH application with all relationships
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
    # If user is a walk-in, always allow submission
    if user and user.application and user.application.hackathonapplicant:
        status = user.application.hackathonapplicant.status
        if status in [StatusEnum.WALK_IN, StatusEnum.WALK_IN_SUBMITTED]:
            return True

    # Otherwise, check if within submission time window
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
    POSTMARK_URL = "https://api.postmarkapp.com/email"
    with open(template, "r", encoding="utf-8") as file:
        raw_html = file.read()
        html_template = Template(raw_html)
        html_content = html_template.render(context)
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "X-Postmark-Server-Token": POSTMARK_API_KEY,
    }
    data = {
        "From": "do-not-reply@hackthevalley.io",
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
    response = requests.post(POSTMARK_URL, json=data, headers=headers)
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
    cooldown = timedelta(minutes=120)
    if selected_user.last_activation_email_sent:
        last_sent = selected_user.last_activation_email_sent

        # Convert naive datetime to aware if needed
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
    access_token_expires = timedelta(minutes=60)
    access_token = create_access_token(
        data={
            "sub": str(selected_user.email),
            "fullName": f"{selected_user.first_name} {selected_user.last_name}",
            "firstName": selected_user.first_name,
            "lastName": selected_user.last_name,
            "scopes": scopes,
        },
        SECRET_KEY=SECRET_KEY,
        ALGORITHM=ALGORITHM,
        expires_delta=access_token_expires,
    )
    response = await sendEmail(
        "templates/activation.html",
        email,
        "Account Activation",
        f"Go to this link to activate your account: https://hackthevalley.io/account-activate?token={access_token}",
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
    start_date = date(2025, 10, 3)
    end_date = date(2025, 10, 5)
    date_range_str = f"{start_date.strftime('%b %d')} - {end_date.strftime('%d, %Y')}"
    card_info = EventTicket()
    card_info.add_primary_field("role", "Hacker", "Role")
    card_info.add_secondary_field("name", user_name, "Name")
    card_info.add_secondary_field("date", date_range_str, "Date")
    card_info.add_auxiliary_field(
        "location", "IA building, UofT Scarborough", "Location"
    )
    client = ApplePassGeneratorClient(
        team_identifier=os.getenv("APPLE_TEAM_IDENTIFIER"),
        pass_type_identifier=os.getenv("APPLE_PASS_TYPE_IDENTIFIER"),
        organization_name="Hack the Valley",
    )
    apple_pass = client.get_pass(card_info)
    apple_pass.logo_text = "Hack the Valley X"
    apple_pass.background_color = "rgb(25, 24, 32)"
    apple_pass.foreground_color = "rgb(255,255,255)"
    apple_pass.label_color = "rgb(255, 255, 255)"
    apple_pass.barcode = Barcode(application_id, format=BarcodeFormat.QR)

    # Add required graphics (must exist in pass)
    apple_pass.add_file("icon.png", open("images/icon-29x29.png", "rb"))
    apple_pass.add_file("logo.png", open("images/logo-50x50.png", "rb"))

    # Create signed .pkpass (bytes in memory, not written to disk)
    package = apple_pass.create(
        "certs/apple/cert.pem",
        "certs/apple/key.pem",
        "certs/apple/wwdr.pem",
        os.getenv("APPLE_WALLET_KEY_PASSWORD"),
        None,  # ⚡ keep in memory
    )

    return package


def generate_google_wallet_pass(user_name: str, application_id: str):
    GOOGLE_CREDENTIALS_FILE = "certs/google/credentials.json"
    creds = service_account.Credentials.from_service_account_file(
        GOOGLE_CREDENTIALS_FILE,
        scopes=["https://www.googleapis.com/auth/wallet_object.issuer"],
    )

    issuer_id = os.getenv("GOOGLE_WALLET_ISSUER_ID")
    if not issuer_id:
        raise RuntimeError("GOOGLE_WALLET_ISSUER_ID not set")

    class_id = f"{issuer_id}.{os.getenv('GOOGLE_WALLET_CLASS_ID')}"
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
                    "venue": {"name": "UofT Scarborough"},
                    "textModulesData": [{"header": "Name", "body": user_name}],
                }
            ]
        },
    }

    # google.auth.jwt.encode accepts the signer object (creds.signer) and returns bytes
    token_bytes = google.auth.jwt.encode(creds.signer, payload)
    # decode to str
    token = token_bytes.decode("utf-8")
    save_url = f"https://pay.google.com/gp/v/save/{token}"
    return save_url
