import io

from fastapi import APIRouter, HTTPException
from sqlmodel import select

from app.core.db import SessionDep
from app.models.forms import StatusEnum, WalkInRequest
from app.models.user import Account_User
from app.utils import (
    createapplication,
    createQRCode,
    generate_google_wallet_pass,
    sendEmail,
)

router = APIRouter()


@router.post("/walk-ins")
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

    # Create application if user doesn't have one
    if not user.application:
        user.application = await createapplication(user, session)

    # Ensure hackathonapplicant exists
    if not user.application.hackathonapplicant:
        raise HTTPException(
            status_code=400,
            detail={
                "fallbackMessage": "Application setup incomplete",
                "detail": "Application record exists but is incomplete",
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
                "apple_url": f"apple-wallet/{application_id}",
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
