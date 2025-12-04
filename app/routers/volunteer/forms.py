from fastapi import APIRouter, HTTPException, status
from sqlmodel import select

from app.core.db import SessionDep
from app.models.forms import StatusEnum, WalkInRequest
from app.models.user import Account_User
from app.utils import createapplication, send_rsvp

router = APIRouter()


@router.post("/walk-ins")
async def mark_walkin(request: WalkInRequest, session: SessionDep):
    """
    Mark a user as walk-in based on their email.
    - If status is APPLYING/NOT_APPLIED/None -> set to WALK_IN
    - If status is already submitted (APPLIED, ACCEPTED, etc.) -> set to WALK_IN_SUBMITTED and send RSVP email
    """
    statement = select(Account_User).where(Account_User.email == request.email)
    user = session.exec(statement).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "fallbackMessage": "User not found",
                "detail": "No user with this email exists",
            },
        )

    if not user.application:
        user.application = await createapplication(user, session)

    if not user.application.hackathonapplicant:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "fallbackMessage": "Application setup incomplete",
                "detail": "Application record exists but is incomplete",
            },
        )

    current_status = user.application.hackathonapplicant.status
    application_id = str(user.application.application_id)

    early_statuses = [
        StatusEnum.NOT_APPLIED,
        StatusEnum.APPLYING,
        StatusEnum.ACCOUNT_INACTIVE,
    ]

    if current_status in early_statuses or current_status is None:
        user.application.hackathonapplicant.status = StatusEnum.WALK_IN
        message = f"User {user.email} marked as WALK_IN - they can now complete their application"
        send_email = False
    else:
        user.application.hackathonapplicant.status = StatusEnum.WALK_IN_SUBMITTED
        message = f"User {user.email} marked as WALK_IN_SUBMITTED - RSVP email sent"
        send_email = True

    session.add(user.application.hackathonapplicant)
    session.commit()
    session.refresh(user.application.hackathonapplicant)

    if send_email:
        await send_rsvp(user.email, user.full_name, application_id)

    return {
        "message": message,
        "email": user.email,
        "old_status": current_status.value if current_status else None,
        "new_status": user.application.hackathonapplicant.status.value,
        "rsvp_sent": send_email,
    }
