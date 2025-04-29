import uuid
import enum
from typing import TYPE_CHECKING, Optional, List
from datetime import datetime

from pydantic import BaseModel
from sqlmodel import Field, Relationship, SQLModel, Column, Enum

from app.models.meal import Meal

if TYPE_CHECKING:
    from app.models.user import Account_User

    
class Food_Tracking(SQLModel, table=True):
    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
    )
    user_id: uuid.UUID = Field(foreign_key="account_user.uid", index=True)
    meal_id: uuid.UUID = Field(foreign_key="meal.id", index=True)
    checkin_time: datetime = Field(default_factory=datetime.now)
    
    # Relationships
    user: "Account_User" = Relationship(back_populates="meals")
    meal: "Meal"= Relationship(back_populates="tracking_records")

class Food_TrackingCreate(SQLModel):
    user_id: uuid.UUID
    meal_id: uuid.UUID

class Food_TrackingRead(SQLModel):
    id: uuid.UUID
    user_id: uuid.UUID
    meal_id: uuid.UUID
    checkin_time: datetime
    
    name: Optional[str] = None
