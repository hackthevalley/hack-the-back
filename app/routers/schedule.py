from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select

from app.config import AppConfig
from app.core.db import SessionDep
from app.dependencies.auth import get_current_user
from app.models.forms import StatusEnum
from app.models.schedule import ScheduleEvent
from app.models.user import AccountUser
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


@router.get("/confirmed", response_model=SchedulePublic)
def get_confirmed_schedule(
    session: SessionDep,
    current_user: Annotated[AccountUser, Depends(get_current_user)],
) -> SchedulePublic:
    application = current_user.application
    if (
        application is None
        or application.hacker_applicant is None
        or application.hacker_applicant.status
        not in {
            StatusEnum.ACCEPTED_INVITE,
            StatusEnum.SCANNED_IN,
            StatusEnum.WALK_IN_SUBMITTED,
        }
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Schedule access requires an eligible attendee status",
        )
    return get_schedule(session)
