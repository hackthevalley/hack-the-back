import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ScheduleEventFields(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    location: str | None = Field(default=None, max_length=160)
    starts_at: datetime
    ends_at: datetime

    @field_validator("title")
    @classmethod
    def clean_title(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Title cannot be blank")
        return value

    @field_validator("description", "location")
    @classmethod
    def clean_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class ScheduleEventCreate(ScheduleEventFields):
    pass


class ScheduleEventUpdate(ScheduleEventFields):
    pass


class ScheduleEventPublic(ScheduleEventFields):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class SchedulePublic(BaseModel):
    event_start_at: datetime
    event_end_at: datetime
    events: list[ScheduleEventPublic]
