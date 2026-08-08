import logging
from typing import Any

from fastapi import APIRouter, HTTPException, status
from sqlmodel import select

from app.core.db import SessionDep
from app.models.forms import StatusEnum
from app.models.user import AccountUser
from app.schemas.forms import WalkInRequest
from app.services.applications import create_application
from app.services.email import send_rsvp

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/walk-ins")
def mark_walkin(request: WalkInRequest, session: SessionDep) -> dict[str, Any]:
    statement = select(AccountUser).where(AccountUser.email == request.email)
    user = session.exec(statement).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No user with this email exists",
        )

    if not user.application:
        user.application = create_application(user, session)

    if not user.application.hacker_applicant:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Application record exists but is incomplete",
        )

    current_status = user.application.hacker_applicant.status
    application_id = str(user.application.application_id)

    early_statuses = [
        StatusEnum.NOT_APPLIED,
        StatusEnum.APPLYING,
        StatusEnum.ACCOUNT_INACTIVE,
    ]

    if current_status in early_statuses or current_status is None:
        user.application.hacker_applicant.status = StatusEnum.WALK_IN
        message = f"User {user.email} marked as WALK_IN - they can now complete their application"
        send_email = False
    else:
        user.application.hacker_applicant.status = StatusEnum.WALK_IN_SUBMITTED
        message = f"User {user.email} marked as WALK_IN_SUBMITTED - RSVP email sent"
        send_email = True

    session.add(user.application.hacker_applicant)
    session.commit()
    session.refresh(user.application.hacker_applicant)

    if send_email:
        try:
            send_rsvp(user.email, user.full_name, application_id)
        except Exception:
            logger.exception(
                "Walk-in %s was marked submitted, but its RSVP could not be sent",
                application_id,
            )

    return {
        "message": message,
        "email": user.email,
        "old_status": current_status.value if current_status else None,
        "new_status": user.application.hacker_applicant.status.value,
        "rsvp_sent": send_email,
    }
