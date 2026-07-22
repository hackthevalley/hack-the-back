from datetime import datetime, timedelta, timezone
from typing import Annotated

import bcrypt
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.responses import Response
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import select

from app.config import AppConfig, SecurityConfig
from app.core.db import SessionDep
from app.core.orm import eager_load
from app.models.constants import (
    EmailMessage,
    EmailSubject,
    EmailTemplate,
    TokenScope,
    UserRole,
)
from app.models.forms import Forms_Application, StatusEnum
from app.models.token import Token
from app.models.user import (
    Account_User,
    PasswordReset,
    UserCreate,
    UserPublic,
    UserUpdate,
)
from app.services.auth import (
    create_access_token,
    decode_jwt,
    get_current_user,
    scopes_for_user,
)
from app.services.email import send_activation_email, send_email
from app.services.wallet import generate_apple_wallet_pass

router = APIRouter()

_DUMMY_PASSWORD_HASH = "$2b$12$5GljN3FRaeC4ZllCHoeZwuIaAX6fLi1eSK3hW/MNvIe3W3BPW2c42"
_GENERIC_LOGIN_ERROR = "Invalid email or password"
_GENERIC_ACCOUNT_EMAIL_RESPONSE = {
    "message": "If the account is eligible, an email will be sent shortly."
}


def _invalid_login() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=_GENERIC_LOGIN_ERROR,
        headers={"WWW-Authenticate": "Bearer"},
    )


@router.post("/sessions")
def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()], session: SessionDep
) -> Token:
    statement = select(Account_User).where(Account_User.email == form_data.username)
    selected_user = session.exec(statement).first()
    password_hash = selected_user.password if selected_user else _DUMMY_PASSWORD_HASH
    password_matches = bcrypt.checkpw(
        form_data.password.encode("utf-8"), password_hash.encode("utf-8")
    )
    if selected_user is None:
        raise _invalid_login()

    now = datetime.now(timezone.utc)
    locked_until = selected_user.locked_until
    if locked_until and locked_until.tzinfo is None:
        locked_until = locked_until.replace(tzinfo=timezone.utc)
    is_locked = locked_until is not None and locked_until > now

    if not password_matches or is_locked:
        if not is_locked:
            selected_user.failed_login_attempts += 1
            if (
                selected_user.failed_login_attempts
                >= SecurityConfig.LOGIN_MAX_FAILED_ATTEMPTS
            ):
                selected_user.locked_until = now + timedelta(
                    minutes=SecurityConfig.LOGIN_LOCKOUT_MINUTES
                )
                selected_user.failed_login_attempts = 0
            session.add(selected_user)
            session.commit()
        raise _invalid_login()

    if not selected_user.is_active:
        try:
            send_activation_email(selected_user.email, session)
        except HTTPException:
            pass
        raise _invalid_login()

    if selected_user.failed_login_attempts or selected_user.locked_until:
        selected_user.failed_login_attempts = 0
        selected_user.locked_until = None
        session.add(selected_user)
        session.commit()

    scopes = scopes_for_user(selected_user)
    access_token_expires = timedelta(minutes=SecurityConfig.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={
            "sub": str(selected_user.email),
            "fullName": selected_user.full_name,
            "firstName": selected_user.first_name,
            "lastName": selected_user.last_name,
            "scopes": scopes,
            "ver": selected_user.token_version,
        },
        secret_key=SecurityConfig.SECRET_KEY,
        algorithm=SecurityConfig.ALGORITHM,
        expires_delta=access_token_expires,
    )
    return Token(access_token=access_token, token_type="bearer")


@router.post("/users", status_code=status.HTTP_202_ACCEPTED)
def signup(user: UserCreate, session: SessionDep):
    hashed_password = bcrypt.hashpw(
        user.password.encode("utf-8"), bcrypt.gensalt()
    ).decode("utf-8")
    statement = select(Account_User).where(Account_User.email == user.email)
    selected_user = session.exec(statement).first()
    if selected_user:
        if not selected_user.is_active:
            try:
                send_activation_email(selected_user.email, session)
            except HTTPException:
                pass
        return _GENERIC_ACCOUNT_EMAIL_RESPONSE
    extra_data = {
        "password": hashed_password,
        "role": UserRole.HACKER,
        "is_active": False,
    }
    db_user = Account_User.model_validate(user, update=extra_data)
    session.add(db_user)
    session.commit()
    session.refresh(db_user)
    send_activation_email(user.email, session)
    return _GENERIC_ACCOUNT_EMAIL_RESPONSE


@router.get("/me", response_model=UserPublic)
def read_users_me(
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
def send_reset_password(
    user: PasswordReset, session: SessionDep, background_tasks: BackgroundTasks
):
    statement = select(Account_User).where(Account_User.email == user.email)
    selected_user = session.exec(statement).first()
    if not selected_user:
        return _GENERIC_ACCOUNT_EMAIL_RESPONSE
    now = datetime.now(timezone.utc)
    cooldown = timedelta(minutes=SecurityConfig.PASSWORD_RESET_COOLDOWN_MINUTES)
    if selected_user.last_password_reset_request:
        last_sent = selected_user.last_password_reset_request
        if last_sent.tzinfo is None:
            last_sent = last_sent.replace(tzinfo=timezone.utc)
        if now - last_sent < cooldown:
            return _GENERIC_ACCOUNT_EMAIL_RESPONSE

    selected_user.last_password_reset_request = now
    session.add(selected_user)
    session.commit()
    scopes = []
    scopes.append(TokenScope.RESET_PASSWORD.value)
    access_token_expires = timedelta(
        minutes=SecurityConfig.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES
    )
    access_token = create_access_token(
        data={
            "sub": str(selected_user.email),
            "fullName": selected_user.full_name,
            "firstName": selected_user.first_name,
            "lastName": selected_user.last_name,
            "scopes": scopes,
            "ver": selected_user.token_version,
        },
        secret_key=SecurityConfig.SECRET_KEY,
        algorithm=SecurityConfig.ALGORITHM,
        expires_delta=access_token_expires,
    )
    password_reset_url = AppConfig.get_password_reset_url(access_token)
    background_tasks.add_task(
        send_email,
        EmailTemplate.PASSWORD_RESET,
        user.email,
        EmailSubject.PASSWORD_RESET,
        EmailMessage.password_reset_text(password_reset_url),
        {"url": access_token},
    )
    return _GENERIC_ACCOUNT_EMAIL_RESPONSE


@router.put("/password-resets")
def reset_password(user: UserUpdate, session: SessionDep):
    if user.password is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Password is required",
        )
    token_data = decode_jwt(user.token)
    if TokenScope.RESET_PASSWORD.value not in token_data.scopes:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type"
        )
    statement = select(Account_User).where(Account_User.email == token_data.email)
    selected_user = session.exec(statement).first()

    if not selected_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    if token_data.token_version != selected_user.token_version:
        raise _invalid_login()

    selected_user.password = bcrypt.hashpw(
        user.password.encode("utf-8"), bcrypt.gensalt()
    ).decode("utf-8")
    selected_user.token_version += 1
    selected_user.failed_login_attempts = 0
    selected_user.locked_until = None
    session.add(selected_user)
    session.commit()
    session.refresh(selected_user)
    return True


@router.post("/activations")
def activate(user: UserUpdate, session: SessionDep):
    token_data = decode_jwt(user.token)
    if TokenScope.ACCOUNT_ACTIVATE.value not in token_data.scopes:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type"
        )
    statement = select(Account_User).where(Account_User.email == token_data.email)
    selected_user = session.exec(statement).first()

    if not selected_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    if token_data.token_version != selected_user.token_version:
        raise _invalid_login()

    selected_user.is_active = True
    selected_user.token_version += 1
    session.add(selected_user)
    session.commit()
    session.refresh(selected_user)
    return True


@router.post("/tokens")
def refresh(
    current_user: Annotated[Account_User, Depends(get_current_user)],
) -> Token:
    access_token_expires = timedelta(minutes=SecurityConfig.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={
            "sub": str(current_user.email),
            "scopes": scopes_for_user(current_user),
            "ver": current_user.token_version,
        },
        secret_key=SecurityConfig.SECRET_KEY,
        algorithm=SecurityConfig.ALGORITHM,
        expires_delta=access_token_expires,
    )
    return Token(access_token=access_token, token_type="bearer")


@router.get("/apple-wallet/{application_id}")
def apple_wallet(application_id: str, session: SessionDep):
    statement = (
        select(Account_User.first_name, Account_User.last_name)
        .join(Forms_Application, Forms_Application.uid == Account_User.uid)
        .where(Forms_Application.application_id == application_id)
    )
    result = session.exec(statement).first()
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Application not found"
        )

    pkpass_bytes_io = generate_apple_wallet_pass(
        f"{result[0]} {result[1]}", application_id
    )
    if hasattr(pkpass_bytes_io, "getvalue"):
        pkpass_bytes = pkpass_bytes_io.getvalue()
    else:
        pkpass_bytes = pkpass_bytes_io

    return Response(
        content=pkpass_bytes,
        media_type="application/vnd.apple.pkpass",
        headers={
            "Content-Disposition": f'attachment; filename="ticket_{application_id}.pkpass"'
        },
    )


@router.patch("/rsvp-status")
def rsvp_status_update(
    status: StatusEnum,
    current_user: Annotated[Account_User, Depends(get_current_user)],
    session: SessionDep,
):
    application_statement = (
        select(Forms_Application)
        .where(Forms_Application.uid == current_user.uid)
        .options(eager_load(Forms_Application.hackathonapplicant))
    )
    application = session.exec(application_statement).first()

    if not application:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Application not found"
        )

    hacker_applicant = application.hackathonapplicant
    if hacker_applicant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Applicant status not found"
        )

    if hacker_applicant.status != StatusEnum.ACCEPTED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only accepted applications can update RSVP status",
        )

    try:
        hacker_applicant.status = status.value
        application.updated_at = datetime.now(timezone.utc)

        session.add(hacker_applicant)
        session.add(application)
        session.commit()
        session.refresh(hacker_applicant)
        session.refresh(application)
    except Exception as e:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update RSVP status: {str(e)}",
        )

    return {"new_status": status.value}
