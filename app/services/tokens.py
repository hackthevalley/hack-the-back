from datetime import datetime, timedelta, timezone

import jwt
from jwt.exceptions import InvalidTokenError

from app.config import SecurityConfig
from app.core.errors import ServiceError
from app.models.constants import TokenScope, UserRole
from app.models.user import AccountUser
from app.schemas.token import TokenData


def decode_token(token: str) -> TokenData:
    try:
        payload = jwt.decode(
            token, SecurityConfig.SECRET_KEY, algorithms=[SecurityConfig.ALGORITHM]
        )
        email = payload.get("sub")
        scopes = payload.get("scopes", [])
        token_version = payload.get("ver")
        if (
            not isinstance(email, str)
            or not isinstance(scopes, list)
            or type(token_version) is not int
        ):
            raise ServiceError(401, "Invalid credentials or expired token")
        return TokenData(
            email=email,
            fullName=payload.get("fullName"),
            firstName=payload.get("firstName"),
            lastName=payload.get("lastName"),
            scopes=scopes,
            ver=token_version,
        )
    except InvalidTokenError as error:
        raise ServiceError(401, "Invalid credentials or expired token") from error


def scopes_for_user(user: AccountUser) -> list[str]:
    if user.role == UserRole.ADMIN:
        return [TokenScope.ADMIN.value]
    if user.role == UserRole.VOLUNTEER:
        return [TokenScope.VOLUNTEER.value]
    return []


def create_access_token(
    data: dict, secret_key: str, algorithm: str, expires_delta: timedelta | None = None
):
    now = datetime.now(timezone.utc)
    to_encode = data.copy()
    to_encode.update(
        {"iat": now, "exp": now + (expires_delta or timedelta(minutes=1))}
    )
    return jwt.encode(to_encode, secret_key, algorithm=algorithm)


def create_user_access_token(
    user: AccountUser, scopes: list[str], expires_delta: timedelta
) -> str:
    return create_access_token(
        data={
            "sub": str(user.email),
            "fullName": user.full_name,
            "firstName": user.first_name,
            "lastName": user.last_name,
            "scopes": scopes,
            "ver": user.token_version,
        },
        secret_key=SecurityConfig.SECRET_KEY,
        algorithm=SecurityConfig.ALGORITHM,
        expires_delta=expires_delta,
    )
