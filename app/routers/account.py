from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from passlib.hash import pbkdf2_sha256
from sqlmodel import select

from app.core.db import SessionDep
from app.models.token import Token, TokenData
from app.models.user import (
    Account_User,
    PasswordReset,
    UserCreate,
    UserPublic,
    UserUpdate,
)
from app.utils import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    ALGORITHM,
    SECRET_KEY,
    create_access_token,
    decode_jwt,
    get_current_user,
    sendActivate,
    sendEmail,
)

router = APIRouter()


# Uses type application/x-www-form-urlencoded for response body, not JSON
@router.post("/login")
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()], session: SessionDep
) -> Token:
    statement = select(Account_User).where(Account_User.email == form_data.username)
    selected_user = session.exec(statement).first()
    if not selected_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User does not exist"
        )
    if not pbkdf2_sha256.verify(form_data.password, selected_user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Password is incorrect"
        )
    if not selected_user.is_active:
        await sendActivate(selected_user.email, session)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Account not activated"
        )
    scopes = []
    if selected_user.role == "admin":
        scopes.append("admin")
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
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
    return Token(access_token=access_token, token_type="bearer")


@router.post("/signup", response_model=UserPublic)
async def signup(user: UserCreate, session: SessionDep):
    statement = select(Account_User).where(Account_User.email == user.email)
    selected_user = session.exec(statement).first()
    if selected_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User already exists"
        )
    hashed_password = pbkdf2_sha256.hash(user.password)
    extra_data = {"password": hashed_password, "role": "hacker", "is_active": False}
    db_user = Account_User.model_validate(user, update=extra_data)
    session.add(db_user)
    session.commit()
    session.refresh(db_user)
    await sendActivate(user.email, session)
    return db_user


@router.get("/me", response_model=UserPublic)
async def read_users_me(
    current_user: Annotated[Account_User, Depends(get_current_user)],
):
    application_status = None
    if current_user.application:
        if current_user.application.hackathonapplicant:
            application_status = current_user.application.hackathonapplicant.status
    return UserPublic(
        uid=current_user.uid,
        first_name=current_user.first_name,
        last_name=current_user.last_name,
        email=current_user.email,
        role=current_user.role,
        is_active=current_user.is_active,
        application_status=application_status,
    )


@router.post("/send_reset_password")
async def send_reset_password(user: PasswordReset, session: SessionDep):
    statement = select(Account_User).where(Account_User.email == user.email)
    selected_user = session.exec(statement).first()
    if not selected_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User does not exist"
        )
    now = datetime.now(timezone.utc)
    cooldown = timedelta(minutes=60)
    if selected_user.last_password_reset_request:
        last_sent = selected_user.last_password_reset_request
        if last_sent.tzinfo is None:
            last_sent = last_sent.replace(tzinfo=timezone.utc)
        if now - selected_user.last_password_reset_request < cooldown:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Sent too many emails, please wait before requesting another password reset email.",
            )
    selected_user.last_password_reset_request = now
    session.add(selected_user)
    session.commit()
    scopes = []
    scopes.append("reset_password")
    access_token_expires = timedelta(minutes=15)
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
        "templates/password_reset.html",
        user.email,
        "Account Password Reset",
        f"Go to this link to reset your password: https://hackthevalley.io/reset-password?token={access_token}",
        {"url": access_token},
    )
    return response


@router.post("/reset_password")
async def reset_password(user: UserUpdate, session: SessionDep):
    token_data = await decode_jwt(user.token)
    if "reset_password" not in token_data.scopes:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Wrong token type"
        )
    statement = select(Account_User).where(Account_User.email == token_data.email)
    selected_user = session.exec(statement).first()
    selected_user.password = pbkdf2_sha256.hash(user.password)
    session.add(selected_user)
    session.commit()
    session.refresh(selected_user)
    return True


@router.post("/activate")
async def activate(user: UserUpdate, session: SessionDep):
    token_data = await decode_jwt(user.token)
    if "account_activate" not in token_data.scopes:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Wrong token type"
        )
    statement = select(Account_User).where(Account_User.email == token_data.email)
    selected_user = session.exec(statement).first()
    selected_user.is_active = True
    session.add(selected_user)
    session.commit()
    session.refresh(selected_user)
    await sendEmail(
        "templates/confirmation.html",
        user.email,
        "Account Creation",
        "You have successfully created your account",
        {},
    )
    return True


@router.post("/refresh")
async def refresh(token_data: Annotated[TokenData, Depends(decode_jwt)]) -> Token:
    if "reset_password" in token_data.scopes or "account_activate" in token_data.scopes:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Weak token")
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(token_data.email), "scopes": token_data.scopes},
        SECRET_KEY=SECRET_KEY,
        ALGORITHM=ALGORITHM,
        expires_delta=access_token_expires,
    )
    return Token(access_token=access_token, token_type="bearer")
