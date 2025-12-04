import enum
import uuid
from typing import TYPE_CHECKING, List, Optional

from sqlmodel import Column, Enum, Field, Relationship, SQLModel, UniqueConstraint

if TYPE_CHECKING:
    from app.models.food_tracking import Food_Tracking


class MealType(str, enum.Enum):
    BREAKFAST = "breakfast"
    LUNCH = "lunch"
    DINNER = "dinner"
    SNACK = "snack"
    MERCH = "merch"


class WeekDay(str, enum.Enum):
    FRIDAY = "friday"
    SATURDAY = "saturday"
    SUNDAY = "sunday"


class MealBase(SQLModel):
    day: WeekDay
    meal_type: MealType
    is_active: bool = True


class Meal(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("day", "meal_type", name="unique_day_meal_type"),
    )

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
    )
    day: WeekDay = Field(sa_column=Column(Enum(WeekDay)))
    meal_type: MealType = Field(sa_column=Column(Enum(MealType)))
    is_active: bool = Field(default=True)

    @property
    def name(self) -> str:
        return f"{self.day.capitalize()} {self.meal_type.capitalize()}"

    # Relationship
    tracking_records: List["Food_Tracking"] = Relationship(back_populates="meal")


class MealCreate(MealBase):
    pass


class MealRead(MealBase):
    id: uuid.UUID
    name: str


class MealUpdate(SQLModel):
    is_active: Optional[bool] = None
