from datetime import datetime, timedelta, timezone
from typing import Annotated

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import select

from app.core.db import SessionDep
from app.models.constants import TokenScope, UserRole
from app.models.forms import Forms_Application, StatusEnum
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
    generate_apple_wallet_pass,
    get_current_user,
    sendActivate,
    sendEmail,
)

router = APIRouter()


# Uses type application/x-www-form-urlencoded for response body, not JSON
@router.post("/sessions")
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()], session: SessionDep
) -> Token:
    statement = select(Account_User).where(Account_User.email == form_data.username)
    selected_user = session.exec(statement).first()
    if not selected_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User does not exist"
        )
    if not bcrypt.checkpw(
        form_data.password.encode("utf-8"), selected_user.password.encode("utf-8")
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Password is incorrect"
        )
    if not selected_user.is_active:
        await sendActivate(selected_user.email, session)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Account not activated"
        )
    scopes = []
    if selected_user.role == UserRole.ADMIN:
        scopes.append(TokenScope.ADMIN.value)
    if selected_user.role == UserRole.VOLUNTEER:
        scopes.append(TokenScope.VOLUNTEER.value)
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


@router.post("/users", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
async def signup(user: UserCreate, session: SessionDep):
    statement = select(Account_User).where(Account_User.email == user.email)
    selected_user = session.exec(statement).first()
    if selected_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="User already exists"
        )
    hashed_password = bcrypt.hashpw(
        user.password.encode("utf-8"), bcrypt.gensalt()
    ).decode("utf-8")
    extra_data = {
        "password": hashed_password,
        "role": UserRole.HACKER,
        "is_active": False,
    }
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


@router.post("/password-resets")
async def send_reset_password(user: PasswordReset, session: SessionDep):
    statement = select(Account_User).where(Account_User.email == user.email)
    selected_user = session.exec(statement).first()
    if not selected_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User does not exist"
        )
    now = datetime.now(timezone.utc)
    cooldown = timedelta(minutes=15)
    if selected_user.last_password_reset_request:
        last_sent = selected_user.last_password_reset_request
        if last_sent.tzinfo is None:
            last_sent = last_sent.replace(tzinfo=timezone.utc)
        if now - last_sent < cooldown:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Sent too many emails, please wait before requesting another password reset email.",
            )

    selected_user.last_password_reset_request = now
    session.add(selected_user)
    session.commit()
    scopes = []
    scopes.append(TokenScope.RESET_PASSWORD.value)
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


@router.put("/password-resets")
async def reset_password(user: UserUpdate, session: SessionDep):
    token_data = await decode_jwt(user.token)
    if TokenScope.RESET_PASSWORD.value not in token_data.scopes:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type"
        )
    statement = select(Account_User).where(Account_User.email == token_data.email)
    selected_user = session.exec(statement).first()
    selected_user.password = bcrypt.hashpw(
        user.password.encode("utf-8"), bcrypt.gensalt()
    ).decode("utf-8")
    session.add(selected_user)
    session.commit()
    session.refresh(selected_user)
    return True


@router.post("/activations")
async def activate(user: UserUpdate, session: SessionDep):
    token_data = await decode_jwt(user.token)
    if TokenScope.ACCOUNT_ACTIVATE.value not in token_data.scopes:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type"
        )
    statement = select(Account_User).where(Account_User.email == token_data.email)
    selected_user = session.exec(statement).first()
    selected_user.is_active = True
    session.add(selected_user)
    session.commit()
    session.refresh(selected_user)
    return True


@router.post("/tokens")
async def refresh(token_data: Annotated[TokenData, Depends(decode_jwt)]) -> Token:
    if (
        TokenScope.RESET_PASSWORD.value in token_data.scopes
        or TokenScope.ACCOUNT_ACTIVATE.value in token_data.scopes
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token type not eligible for refresh",
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(token_data.email), "scopes": token_data.scopes},
        SECRET_KEY=SECRET_KEY,
        ALGORITHM=ALGORITHM,
        expires_delta=access_token_expires,
    )
    return Token(access_token=access_token, token_type="bearer")


@router.get("/apple-wallet/{application_id}")
async def apple_wallet(application_id: str, session: SessionDep):
    statement = (
        select(Account_User.first_name, Account_User.last_name)
        .join(Forms_Application, Forms_Application.uid == Account_User.uid)
        .where(Forms_Application.application_id == application_id)
    )
    result = session.exec(statement).first()
    if not result:
        return None
    pkpass_bytes_io = generate_apple_wallet_pass(
        f"{result[0]} {result[1]}", application_id
    )
    if hasattr(pkpass_bytes_io, "getvalue"):
        pkpass_bytes = pkpass_bytes_io.getvalue()
    else:
        pkpass_bytes = pkpass_bytes_io  # already bytes

    return Response(
        content=pkpass_bytes,
        media_type="application/vnd.apple.pkpass",
        headers={
            "Content-Disposition": f'attachment; filename="ticket_{application_id}.pkpass"'
        },
    )


@router.patch("/users/{uid}/rsvp-status")
async def rsvp_status_update(uid: str, status: StatusEnum, session: SessionDep):
    application_statement = select(Forms_Application).where(
        Forms_Application.uid == uid
    )
    application = session.exec(application_statement).first()

    if not application:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Application not found"
        )

    if application.hackathonapplicant.status != StatusEnum.ACCEPTED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only accepted applications can update RSVP status",
        )

    application.hackathonapplicant.status = status.value
    application.updated_at = datetime.now(timezone.utc)

    session.add(application.hackathonapplicant)
    session.add(application)
    session.commit()
    session.refresh(application.hackathonapplicant)
    session.refresh(application)

    return {"new_status": status.value}
