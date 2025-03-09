import os
from datetime import datetime, timedelta, timezone
from typing import Annotated

import jwt
from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError
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
    statement = select(Account_User).where(Account_User.email == token_data.email)
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
    current_user: Annotated[Account_User, Depends(get_current_user)],
    session: SessionDep,
):
    application = Forms_Application(
        user=current_user,
        is_draft=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    hackathon_applicant = Forms_HackathonApplicant(
        applicant=application, status=StatusEnum.APPLYING
    )
    db_hackathon_applicant = Forms_HackathonApplicant.model_validate(
        hackathon_applicant
    )
    session.add(db_hackathon_applicant)
    session.commit()
    session.refresh(db_hackathon_applicant)
    statement = select(Forms_Question)
    questions = session.exec(statement)
    for question in questions:
        if "resume" not in question.label.lower():
            answer = Forms_Answer(answer=None, question_id=question.question_id)
            if "first name" in question.label.lower():
                answer.answer = current_user.first_name
            elif "last name" in question.label.lower():
                answer.answer = current_user.last_name
            elif "email" in question.label.lower():
                answer.answer = current_user.email
            db_answer = Forms_Answer.model_validate(answer)
            application.form_answers.append(db_answer)
        else:
            answerfile = Forms_AnswerFile(
                original_filename=None,
                file=None,
                question_id=question.question_id,
            )
            db_answerfile = Forms_AnswerFile.model_validate(answerfile)
            application.form_answersfile = db_answerfile
    session.add(application)
    session.commit()
    return current_user.application


async def isValidSubmissionTime(session: SessionDep):
    time = session.exec(select(Forms_Form).limit(1)).first()
    if time is None:
        return False
    return time.start_at < datetime.now(timezone.utc) < time.end_at
