import io
from datetime import datetime
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Body, HTTPException, status
from pydantic import BaseModel
from sqlmodel import select

from app.core.db import SessionDep
from app.models.forms import Forms_Form, StatusEnum
from app.models.user import Account_User
from app.utils import createQRCode, generate_google_wallet_pass, sendEmail

router = APIRouter()


class WalkInRequest(BaseModel):
    email: str


@router.post("/setregtimerange", response_model=Forms_Form)
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

    # Sanity check for valid correct new time range
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


@router.post("/walkin")
async def mark_walkin(request: WalkInRequest, session: SessionDep):
    """
    Mark a user as walk-in based on their email.
    - If status is APPLYING/NOT_APPLIED/None -> set to WALK_IN
    - If status is already submitted (APPLIED, ACCEPTED, etc.) -> set to WALK_IN_SUBMITTED and send RSVP email
    """
    # Find user by email
    statement = select(Account_User).where(Account_User.email == request.email)
    user = session.exec(statement).first()

    if not user:
        raise HTTPException(
            status_code=404,
            detail={
                "fallbackMessage": "User not found",
                "detail": "No user with this email exists",
            },
        )

    # Check if user has an application
    if not user.application or not user.application.hackathonapplicant:
        raise HTTPException(
            status_code=400,
            detail={
                "fallbackMessage": "User has no application",
                "detail": "User needs to create an application first",
            },
        )

    current_status = user.application.hackathonapplicant.status
    application_id = str(user.application.application_id)

    # Determine new status based on current status
    early_statuses = [
        StatusEnum.NOT_APPLIED,
        StatusEnum.APPLYING,
        StatusEnum.ACCOUNT_INACTIVE,
    ]

    if current_status in early_statuses or current_status is None:
        # User hasn't submitted yet - mark as WALK_IN (can still fill out application)
        user.application.hackathonapplicant.status = StatusEnum.WALK_IN
        message = f"User {user.email} marked as WALK_IN - they can now complete their application"
        send_email = False
    else:
        # User already submitted or further along - mark as WALK_IN_SUBMITTED and send RSVP
        user.application.hackathonapplicant.status = StatusEnum.WALK_IN_SUBMITTED
        message = f"User {user.email} marked as WALK_IN_SUBMITTED - RSVP email sent"
        send_email = True

    # Save status change
    session.add(user.application.hackathonapplicant)
    session.commit()
    session.refresh(user.application.hackathonapplicant)

    # Send RSVP email if needed
    if send_email:
        img = await createQRCode(application_id)
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="PNG")
        img_bytes.seek(0)

        google_link = generate_google_wallet_pass(
            f"{user.first_name} {user.last_name}", application_id
        )

        await sendEmail(
            "templates/rsvp.html",
            user.email,
            "RSVP for Hack the Valley X",
            "RSVP at hackthevalley.io",
            {
                "start_date": "October 3rd 2025",
                "end_date": "October 5th 2025",
                "due_date": "September 26th 2025",
                "apple_url": f"apple_wallet/{application_id}",
                "google_url": f"{google_link}",
            },
            attachments=[("qr_code", img_bytes, "image/png")],
        )

    return {
        "message": message,
        "email": user.email,
        "old_status": current_status.value if current_status else None,
        "new_status": user.application.hackathonapplicant.status.value,
        "rsvp_sent": send_email,
    }
