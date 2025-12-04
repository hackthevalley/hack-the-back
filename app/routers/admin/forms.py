from datetime import datetime
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Body, HTTPException, status
from sqlmodel import select

from app.core.db import SessionDep
from app.models.forms import Forms_Form

router = APIRouter()


@router.put("/registration-timerange", response_model=Forms_Form)
async def set_reg_time_range(
    session: SessionDep,
    start_at: Annotated[str, Body()],
    end_at: Annotated[str, Body()],
) -> Forms_Form:
    """
    Update the hackathon registration time range.

    Args:
        session (SessionDep): Database session dependency.
        start_at (str): Start date for hackathon registration.
        end_at (str): End date for hackathon registration.

    Returns:
        Forms_Form: The current registration time range for Hack the Valley Hackathon.
    """
    current_est_time = datetime.now(ZoneInfo("America/New_York"))
    try:
        new_start_date = (
            datetime.strptime(start_at, "%Y-%m-%d")
            .replace(tzinfo=ZoneInfo("UTC"))
            .astimezone(ZoneInfo("America/New_York"))
        )
        new_end_date = (
            datetime.strptime(end_at, "%Y-%m-%d")
            .replace(tzinfo=ZoneInfo("UTC"))
            .astimezone(ZoneInfo("America/New_York"))
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid date format"
        )

    if new_start_date >= new_end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid time range"
        )

    current_time_range = session.exec(select(Forms_Form)).first()
    if not current_time_range:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Data not found"
        )

    current_time_range.updated_at = current_est_time
    current_time_range.start_at = new_start_date
    current_time_range.end_at = new_end_date

    session.add(current_time_range)
    session.commit()
    session.refresh(current_time_range)

    return current_time_range
