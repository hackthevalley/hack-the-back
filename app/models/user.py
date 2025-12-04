import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from pydantic import BaseModel
from sqlmodel import Field, Relationship, SQLModel

from app.models.constants import UserRole
from app.models.food_tracking import Food_Tracking

if TYPE_CHECKING:
    from app.models.forms import Forms_Application


class UserBase(SQLModel):
    first_name: str = Field(index=True)
    last_name: str = Field(index=True)
    email: str = Field(unique=True, index=True)


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


class UserCreate(UserBase):
    password: str


class UserPublic(UserBase):
    uid: uuid.UUID
    role: UserRole
    is_active: bool
    application_status: Optional[str] = None


class UserUpdate(BaseModel):
    token: str
    password: Optional[str] = None


class PasswordReset(BaseModel):
    email: str
