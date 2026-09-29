from fastapi import APIRouter
from sqlmodel import select

from app.config import AppConfig
from app.core.db import SessionDep
from app.models.schedule import ScheduleEvent
from app.schemas.schedule import SchedulePublic

router = APIRouter()


@router.get("", response_model=SchedulePublic)
def get_schedule(session: SessionDep) -> SchedulePublic:
    events = session.exec(
        select(ScheduleEvent).order_by(ScheduleEvent.starts_at, ScheduleEvent.ends_at)
    ).all()
    return SchedulePublic(
        event_start_at=AppConfig.EVENT_START_DATE,
        event_end_at=AppConfig.EVENT_END_DATE,
        events=list(events),
    )
