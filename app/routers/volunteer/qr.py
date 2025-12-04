from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlmodel import func, select

from app.core.db import SessionDep
from app.models.food_tracking import Food_Tracking
from app.models.forms import (
    Forms_Answer,
    Forms_Application,
    Forms_HackathonApplicant,
    Forms_Question,
    StatusEnum,
)
from app.models.meal import Meal
from app.models.user import Account_User

router = APIRouter()


class QRScanRequest(BaseModel):
    id: str  # application_id


@router.post("")
async def scan_qr(request: QRScanRequest, session: SessionDep):
    """
    Scan QR code to admit a hacker and retrieve their information
    """
    try:
        application_id = UUID(request.id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "fallbackMessage": "Invalid QR code format",
                "detail": "Invalid application ID format",
            },
        )

    statement = (
        select(Forms_Application, Account_User, Forms_HackathonApplicant)
        .join(Account_User, Forms_Application.uid == Account_User.uid)
        .join(
            Forms_HackathonApplicant,
            Forms_Application.application_id == Forms_HackathonApplicant.application_id,
        )
        .where(Forms_Application.application_id == application_id)
    )
    result = session.exec(statement).first()

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "fallbackMessage": "Application not found",
                "detail": "No application found with this QR code",
            },
        )

    application, user, hacker_applicant = result

    if not hacker_applicant.can_scan_in():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "fallbackMessage": f"User cannot be scanned in (Status: {hacker_applicant.status.value})",
                "detail": f"User with status {hacker_applicant.status.value} is not eligible for check-in",
            },
        )

    message = ""

    if (
        hacker_applicant.status == StatusEnum.ACCEPTED
        or hacker_applicant.status == StatusEnum.ACCEPTED_INVITE
    ):
        hacker_applicant.status = StatusEnum.SCANNED_IN
        message = f"Welcome {user.first_name}!"
    elif (
        hacker_applicant.status == StatusEnum.WALK_IN
        or hacker_applicant.status == StatusEnum.WALK_IN_SUBMITTED
    ):
        hacker_applicant.status = StatusEnum.WALK_IN_SUBMITTED
        message = f"Welcome walk-in {user.first_name}!"
    else:
        message = f"Already scanned in: {user.first_name}!"

    session.add(hacker_applicant)
    session.commit()
    session.refresh(hacker_applicant)

    answers_statement = (
        select(Forms_Answer, Forms_Question)
        .join(Forms_Question, Forms_Answer.question_id == Forms_Question.question_id)
        .where(Forms_Answer.application_id == application_id)
    )
    answers_results = session.exec(answers_statement).all()

    answers_dict = {
        "firstName": user.first_name,
        "lastName": user.last_name,
        "email": user.email,
    }

    label_to_key = {
        "Phone Number": "phoneNumber",
        "Dietary Restrictions": "dietaryRestrictions",
        "T-Shirt Size": "tShirtSize",
    }

    for answer, question in answers_results:
        key = label_to_key.get(question.label, question.label.lower().replace(" ", ""))
        answers_dict[key] = answer.answer

    food_tracking_statement = (
        select(Food_Tracking, Meal)
        .join(Meal, Food_Tracking.meal_id == Meal.id)
        .where(Food_Tracking.user_id == user.uid)
    )
    food_results = session.exec(food_tracking_statement).all()

    food_list = []
    for tracking, meal in food_results:
        food_list.append(
            {
                "id": str(tracking.id),
                "serving": str(tracking.meal_id),
                "name": meal.name,
                "day": meal.day.value,
                "meal_type": meal.meal_type.value,
            }
        )

    scanned_count = session.exec(
        select(func.count(Forms_HackathonApplicant.application_id)).where(
            Forms_HackathonApplicant.status == StatusEnum.SCANNED_IN
        )
    ).one()

    walkin_count = session.exec(
        select(func.count(Forms_HackathonApplicant.application_id)).where(
            Forms_HackathonApplicant.status.in_(
                [StatusEnum.WALK_IN, StatusEnum.WALK_IN_SUBMITTED]
            )
        )
    ).one()

    response_body = {
        "id": str(application_id),
        "answers": answers_dict,
        "food": food_list,
        "applicant": {
            "status": hacker_applicant.status.value,
            "application_id": str(application_id),
        },
    }

    return {
        "message": message,
        "body": response_body,
        "scannedCount": scanned_count,
        "walkinCount": walkin_count,
    }
