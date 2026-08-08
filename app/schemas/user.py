import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.constants import UserRole
from app.validators import (
    PASSWORD_MAX_LENGTH,
    PASSWORD_MIN_LENGTH,
    validate_password_requirements,
)


class UserBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    email: EmailStr = Field(max_length=255)


class UserCreate(UserBase):
    password: str = Field(min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH)

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, value: str) -> str:
        return validate_password_requirements(value)


class UserPublic(UserBase):
    uid: uuid.UUID
    role: UserRole
    is_active: bool
    application_status: str | None = None


class UserUpdate(BaseModel):
    token: str = Field(max_length=1000)
    password: str | None = Field(
        None, min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH
    )

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, value: str | None) -> str | None:
        return value if value is None else validate_password_requirements(value)


class PasswordReset(BaseModel):
    email: EmailStr = Field(max_length=255)
