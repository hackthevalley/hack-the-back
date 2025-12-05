from datetime import datetime
from typing import Annotated

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
        start_at (str): Start date for hackathon registration (format: YYYY-MM-DD).
        end_at (str): End date for hackathon registration (format: YYYY-MM-DD).

    Returns:
        Forms_Form: The current registration time range for Hack the Valley Hackathon.

    Note:
        Dates are stored in UTC. Times should be parsed as UTC and will be
        displayed in the appropriate timezone by the frontend.
    """
    from datetime import timezone as tz

    current_utc_time = datetime.now(tz.utc)
    try:
        # Parse dates as UTC for consistency
        new_start_date = datetime.strptime(start_at, "%Y-%m-%d").replace(tzinfo=tz.utc)
        new_end_date = datetime.strptime(end_at, "%Y-%m-%d").replace(tzinfo=tz.utc)
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

    current_time_range.updated_at = current_utc_time
    current_time_range.start_at = new_start_date
    current_time_range.end_at = new_end_date

    session.add(current_time_range)
    session.commit()
    session.refresh(current_time_range)

    from app.cache import cache

    cache.delete("registration_timerange")

    return current_time_range
