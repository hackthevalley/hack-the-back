import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Response, status
from sqlmodel import select

from app.config import AppConfig
from app.core.db import SessionDep
from app.models.schedule import ScheduleEvent
from app.schemas.schedule import (
    ScheduleEventCreate,
    ScheduleEventPublic,
    ScheduleEventUpdate,
)

router = APIRouter()


def validate_event_window(starts_at: datetime, ends_at: datetime) -> None:
    if starts_at.tzinfo is None or ends_at.tzinfo is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Event times must include a timezone",
        )
    starts_at = starts_at.astimezone(timezone.utc)
    ends_at = ends_at.astimezone(timezone.utc)
    event_start = AppConfig.EVENT_START_DATE.astimezone(timezone.utc)
    event_end = AppConfig.EVENT_END_DATE.astimezone(timezone.utc)
    if starts_at >= ends_at:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Event end time must be after its start time",
        )
    if starts_at < event_start or ends_at > event_end:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Event must be within the configured hackathon start and end times",
        )


def get_event_or_404(session: SessionDep, event_id: uuid.UUID) -> ScheduleEvent:
    event = session.get(ScheduleEvent, event_id)
    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Schedule event not found"
        )
    return event


@router.get("", response_model=list[ScheduleEventPublic])
def list_events(session: SessionDep) -> list[ScheduleEvent]:
    return list(
        session.exec(
            select(ScheduleEvent).order_by(
                ScheduleEvent.starts_at, ScheduleEvent.ends_at
            )
        ).all()
    )


@router.post(
    "", response_model=ScheduleEventPublic, status_code=status.HTTP_201_CREATED
)
def create_event(payload: ScheduleEventCreate, session: SessionDep) -> ScheduleEvent:
    validate_event_window(payload.starts_at, payload.ends_at)
    event = ScheduleEvent.model_validate(payload)
    session.add(event)
    session.commit()
    session.refresh(event)
    return event


@router.put("/{event_id}", response_model=ScheduleEventPublic)
def update_event(
    event_id: uuid.UUID, payload: ScheduleEventUpdate, session: SessionDep
) -> ScheduleEvent:
    validate_event_window(payload.starts_at, payload.ends_at)
    event = get_event_or_404(session, event_id)
    for field, value in payload.model_dump().items():
        setattr(event, field, value)
    event.updated_at = datetime.now(timezone.utc)
    session.add(event)
    session.commit()
    session.refresh(event)
    return event


@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_event(event_id: uuid.UUID, session: SessionDep) -> Response:
    event = get_event_or_404(session, event_id)
    session.delete(event)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
