from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from passlib.hash import pbkdf2_sha256
from sqlmodel import select

from app.core.db import SessionDep
from app.models.token import Token, TokenData
from app.models.user import Account_User, UserCreate, UserPublic
from app.utils import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    ALGORITHM,
    SECRET_KEY,
    create_access_token,
    decode_jwt,
    get_current_user,
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
    return db_user


@router.get("/me", response_model=UserPublic)
async def read_users_me(
    current_user: Annotated[Account_User, Depends(get_current_user)],
):
    return current_user


@router.get("/reset_password")
async def reset_password():
    return {"username": "fakecurrentuser"}


@router.post("/activate")
async def activate():
    return {"username": "fakecurrentuser"}


@router.post("/refresh")
async def refresh(token_data: Annotated[TokenData, Depends(decode_jwt)]) -> Token:
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(token_data.email), "scopes": token_data.scopes},
        SECRET_KEY=SECRET_KEY,
        ALGORITHM=ALGORITHM,
        expires_delta=access_token_expires,
    )
    return Token(access_token=access_token, token_type="bearer")
