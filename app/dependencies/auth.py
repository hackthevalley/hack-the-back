from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlmodel import select

from app.core.db import SessionDep
from app.core.orm import eager_load
from app.core.errors import ServiceError
from app.models.constants import TokenScope
from app.models.forms import FormApplication
from app.models.user import AccountUser
from app.schemas.token import TokenData
from app.services.tokens import decode_token

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/account/sessions",
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


def decode_jwt(token: Annotated[str, Depends(oauth2_scheme)]) -> TokenData:
    try:
        return decode_token(token)
    except ServiceError as error:
        raise credentials_exception from error


def get_current_user(
    token_data: Annotated[TokenData, Depends(decode_jwt)], session: SessionDep
) -> AccountUser:
    if (
        TokenScope.RESET_PASSWORD.value in token_data.scopes
        or TokenScope.ACCOUNT_ACTIVATE.value in token_data.scopes
    ):
        raise credentials_exception
    user = session.exec(
        select(AccountUser)
        .where(AccountUser.email == token_data.email)
        .options(
            eager_load(AccountUser.application).joinedload(
                FormApplication.hacker_applicant
            )
        )
    ).first()
    if (
        user is None
        or not user.is_active
        or user.token_version != token_data.token_version
    ):
        raise credentials_exception
    return user
