from typing import Annotated
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Body, status
from sqlmodel import select

from app.core.db import SessionDep
from app.models.forms import Forms_ApplicationTimeRange

router = APIRouter()

@router.get("/getregtimerange", response_model=Forms_ApplicationTimeRange)
async def get_reg_time_range(
    session: SessionDep
) -> Forms_ApplicationTimeRange:
    """
    Retrieve the current hackathon registration time range.

    Args:
        session (SessionDep): Database session dependency.

    Returns:
        Forms_ApplicationTimeRange: The current registration time range for Hack the Valley Hackathon.
    """
    time_range = session.exec(select(Forms_ApplicationTimeRange)).first()
    return time_range


@router.post("/setregtimerange", response_model=Forms_ApplicationTimeRange)
async def set_reg_time_range(
    session: SessionDep,
    start_at: Annotated[str, Body()],
    end_at: Annotated[str, Body()],
) -> Forms_ApplicationTimeRange:
    """
    Update the hackathon registration time range.

    Args:
        session (SessionDep): Database session dependency.
        start_at (str): Start date for hackathon registration.
        end_at (str): End date for hackathon registration.

    Returns:
        Forms_ApplicationTimeRange: The current registration time range for Hack the Valley Hackathon.
    """
    current_est_time = datetime.now(ZoneInfo("America/New_York"))
    try:
        new_start_date = datetime.strptime(start_at, "%Y-%m-%d").replace(tzinfo=ZoneInfo("UTC")).astimezone(ZoneInfo("America/New_York"))
        new_end_date = datetime.strptime(end_at, "%Y-%m-%d").replace(tzinfo=ZoneInfo("UTC")).astimezone(ZoneInfo("America/New_York"))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid date format, should be YYYY-MM-DD")
    
    if (new_start_date >= new_end_date):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Start date must be before end date")

    current_time_range = session.exec(select(Forms_ApplicationTimeRange)).first()
    if not current_time_range:
        current_time_range = Forms_ApplicationTimeRange(
            created_at= current_est_time,
            updated_at= current_est_time,
            start_at= new_start_date,
            end_at= new_end_date
        )
    else:
        current_time_range.updated_at = current_est_time
        current_time_range.start_at = new_start_date
        current_time_range.end_at = new_end_date

    session.add(current_time_range)
    session.commit()
    session.refresh(current_time_range)
    
    return current_time_range
