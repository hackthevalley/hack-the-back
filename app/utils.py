import os
from datetime import datetime, timedelta, timezone
from typing import Annotated

import jwt
import requests
from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jinja2 import Template
from jwt.exceptions import InvalidTokenError
from sqlalchemy.orm import selectinload
from sqlmodel import select

from app.core.db import SessionDep
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
        "admin": "Allow user to call admin routes",
        "volunteer": "Allow user to call qr routes",
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
    if "reset_password" in token_data.scopes or "account_activate" in token_data.scopes:
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
    # Ensure user has required fields BEFORE anything else
    if not all([current_user.first_name, current_user.last_name, current_user.email]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User profile incomplete - missing first name, last name, or email",
        )

    # Create application object
    application = Forms_Application(
        user=current_user,
        is_draft=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    session.add(application)
    session.commit()
    session.refresh(application)

    # Create hackathon applicant entry
    hackathon_applicant = Forms_HackathonApplicant(
        applicant=application,
        status=StatusEnum.APPLYING,
    )
    session.add(hackathon_applicant)
    session.commit()
    session.refresh(hackathon_applicant)

    # Preload all form questions
    questions = session.exec(
        select(Forms_Question).order_by(Forms_Question.question_order)
    ).all()

    answers = []
    resume_question = None
    for q in questions:
        if "resume" not in q.label.lower():
            answer_value = None
            if "first name" in q.label.lower():
                answer_value = current_user.first_name
            elif "last name" in q.label.lower():
                answer_value = current_user.last_name
            elif "email" in q.label.lower():
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

    # Bulk insert answers
    session.add_all(answers)

    # Add resume answer file if needed
    if resume_question:
        resume_answer = Forms_AnswerFile(
            application_id=application.application_id,
            original_filename=None,
            file_path=None,
            question_id=resume_question.question_id,
        )
        session.add(resume_answer)

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


async def isValidSubmissionTime(session: SessionDep):
    time = session.exec(select(Forms_Form).limit(1)).first()
    if time is None:
        return False
    return time.start_at < datetime.now(timezone.utc) < time.end_at


async def sendEmail(
    template: str, receiver: str, subject: str, textbody: str, context: str
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
    scopes.append("account_activate")
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
