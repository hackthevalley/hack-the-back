from datetime import datetime, timedelta, timezone
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError
from sqlmodel import select

from app.config import SecurityConfig
from app.core.db import SessionDep
from app.core.orm import eager_load
from app.models.constants import TokenScope, UserRole
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


def decode_jwt(token: Annotated[str, Depends(oauth2_scheme)]):
    try:
        payload = jwt.decode(
            token, SecurityConfig.SECRET_KEY, algorithms=[SecurityConfig.ALGORITHM]
        )
        email = payload.get("sub")
        scopes: list[str] = payload.get("scopes", [])
        token_version = payload.get("ver")
        if not isinstance(email, str) or type(token_version) is not int:
            raise credentials_exception
        return TokenData(
            email=email,
            fullName=payload.get("fullName"),
            firstName=payload.get("firstName"),
            lastName=payload.get("lastName"),
            scopes=scopes,
            ver=token_version,
        )
    except InvalidTokenError:
        raise credentials_exception


def get_current_user(
    token_data: Annotated[TokenData, Depends(decode_jwt)], session: SessionDep
) -> Account_User:
    if (
        TokenScope.RESET_PASSWORD.value in token_data.scopes
        or TokenScope.ACCOUNT_ACTIVATE.value in token_data.scopes
    ):
        raise credentials_exception

    statement = (
        select(Account_User)
        .where(Account_User.email == token_data.email)
        .options(eager_load(Account_User.application))
    )
    user = session.exec(statement).first()
    if user is None:
        raise credentials_exception
    if not user.is_active or user.token_version != token_data.token_version:
        raise credentials_exception
    return user


def scopes_for_user(user: Account_User) -> list[str]:
    if user.role == UserRole.ADMIN:
        return [TokenScope.ADMIN.value]
    if user.role == UserRole.VOLUNTEER:
        return [TokenScope.VOLUNTEER.value]
    return []


def create_access_token(
    data: dict, secret_key: str, algorithm: str, expires_delta: timedelta | None = None
):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta if expires_delta else timedelta(minutes=1)
    )
    to_encode.update({"iat": datetime.now(timezone.utc), "exp": expire})
    return jwt.encode(to_encode, secret_key, algorithm=algorithm)
