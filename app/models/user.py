import uuid
from typing import TYPE_CHECKING, Optional

from pydantic import BaseModel
from sqlmodel import Field, Relationship, SQLModel

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
    role: str
    is_active: bool
    application: Optional["Forms_Application"] = Relationship(back_populates="user")
    meals: Optional["Food_Tracking"] = Relationship(back_populates="user")


class UserCreate(UserBase):
    password: str


class UserPublic(UserBase):
    uid: uuid.UUID
    role: str
    is_active: bool


class UserUpdate(SQLModel):
    password: str | None = None


class PasswordReset(BaseModel):
    email: str
