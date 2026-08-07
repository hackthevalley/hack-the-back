import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from sqlmodel import Column, DateTime, Field, Relationship, SQLModel, UniqueConstraint

from app.models.meal import Meal

if TYPE_CHECKING:
    from app.models.user import AccountUser


class Food_Tracking(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("user_id", "meal_id", name="uq_food_tracking_user_meal"),
    )

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
    )
    user_id: uuid.UUID = Field(foreign_key="account_user.uid", index=True)
    meal_id: uuid.UUID = Field(foreign_key="meal.id", index=True)
    checkin_time: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            default=lambda: datetime.now(timezone.utc),
        ),
    )

    user: "AccountUser" = Relationship(back_populates="meals")
    meal: "Meal" = Relationship(back_populates="tracking_records")


class Food_TrackingCreate(SQLModel):
    user_id: uuid.UUID
    meal_id: uuid.UUID


class Food_TrackingRead(SQLModel):
    id: uuid.UUID
    user_id: uuid.UUID
    meal_id: uuid.UUID
    checkin_time: datetime

    name: Optional[str] = None
