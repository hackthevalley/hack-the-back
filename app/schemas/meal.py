import uuid

from sqlmodel import SQLModel

from app.models.meal import MealBase


class MealCreate(MealBase):
    pass


class MealRead(MealBase):
    id: uuid.UUID
    name: str


class MealUpdate(SQLModel):
    is_active: bool | None = None
