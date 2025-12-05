import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from pydantic import BaseModel, EmailStr, field_validator
from sqlmodel import Field, Relationship, SQLModel

from app.models.constants import UserRole
from app.models.food_tracking import Food_Tracking

if TYPE_CHECKING:
    from app.models.forms import Forms_Application


class UserBase(SQLModel):
    first_name: str = Field(index=True, min_length=1, max_length=100)
    last_name: str = Field(index=True, min_length=1, max_length=100)
    email: EmailStr = Field(unique=True, index=True, max_length=255)


class Account_User(UserBase, table=True):
    uid: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
    )
    password: str
    role: UserRole
    is_active: bool
    last_password_reset_request: Optional[datetime] = None
    last_activation_email_sent: Optional[datetime] = None
    application: Optional["Forms_Application"] = Relationship(back_populates="user")
    meals: Optional["Food_Tracking"] = Relationship(back_populates="user")

    @property
    def full_name(self) -> str:
        """Get user's full name."""
        return f"{self.first_name} {self.last_name}"


class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """Validate password meets minimum security requirements."""
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one number")
        return v


class UserPublic(UserBase):
    uid: uuid.UUID
    role: UserRole
    is_active: bool
    application_status: Optional[str] = None


class UserUpdate(BaseModel):
    token: str = Field(max_length=1000)
    password: Optional[str] = Field(None, min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: Optional[str]) -> Optional[str]:
        """Validate password meets minimum security requirements."""
        if v is None:
            return v
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one number")
        return v


class PasswordReset(BaseModel):
    email: EmailStr = Field(max_length=255)
