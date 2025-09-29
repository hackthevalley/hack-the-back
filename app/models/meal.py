import uuid
import enum
from typing import TYPE_CHECKING, Optional, List
from datetime import datetime

from pydantic import BaseModel
from sqlmodel import Field, Relationship, SQLModel, Column, Enum


if TYPE_CHECKING:
    from app.models.food_tracking import Food_Tracking

class MealType(str, enum.Enum):
    BREAKFAST = "breakfast"
    LUNCH = "lunch"
    DINNER = "dinner"
    SNACK = "snack"

class WeekDay(str, enum.Enum):
    FRIDAY = "friday"
    SATURDAY = "saturday"
    SUNDAY = "sunday"

class MealBase(SQLModel):
    day: WeekDay
    meal_type: MealType
    is_active: bool = True

class Meal(SQLModel, table=True):
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

