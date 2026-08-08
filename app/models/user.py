import uuid
from datetime import datetime
from typing import TYPE_CHECKING, ClassVar, Optional

from pydantic import EmailStr
from sqlmodel import Column, DateTime, Field, Relationship, SQLModel

from app.models.constants import UserRole
from app.models.food_tracking import FoodTracking

if TYPE_CHECKING:
    from app.models.forms import FormApplication


class UserBase(SQLModel):
    first_name: str = Field(index=True, min_length=1, max_length=100)
    last_name: str = Field(index=True, min_length=1, max_length=100)
    email: EmailStr = Field(unique=True, index=True, max_length=255)


class AccountUser(UserBase, table=True):
    __tablename__: ClassVar[str] = "account_user"

    uid: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
    )
    password: str
    role: UserRole
    is_active: bool
    token_version: int = Field(default=0, nullable=False)
    failed_login_attempts: int = Field(default=0, nullable=False)
    locked_until: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    last_password_reset_request: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    last_activation_email_sent: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    application: Optional["FormApplication"] = Relationship(back_populates="user")
    meals: list["FoodTracking"] = Relationship(back_populates="user")

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"
