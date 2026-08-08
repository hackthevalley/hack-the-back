from uuid import UUID
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlmodel import col, func, select

from app.core.db import SessionDep
from app.models.constants import QuestionLabel
from app.models.food_tracking import FoodTracking
from app.models.forms import (
    FormAnswer,
    FormApplication,
    HackathonApplicant,
    FormQuestion,
    StatusEnum,
)
from app.models.meal import Meal
from app.models.user import AccountUser

router = APIRouter()


class QRScanRequest(BaseModel):
    id: str


@router.post("")
def scan_qr(request: QRScanRequest, session: SessionDep) -> dict[str, Any]:
    try:
        application_id = UUID(request.id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid application ID format",
        )

    statement = (
        select(FormApplication, AccountUser, HackathonApplicant)
        .join(AccountUser, FormApplication.uid == AccountUser.uid)
        .join(
            HackathonApplicant,
            FormApplication.application_id == HackathonApplicant.application_id,
        )
        .where(FormApplication.application_id == application_id)
    )
    result = session.exec(statement).first()

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No application found with this QR code",
        )

    application, user, hacker_applicant = result

    if not hacker_applicant.can_scan_in():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"User with status {hacker_applicant.status.value} "
                "is not eligible for check-in"
            ),
        )

    message = ""

    if (
        hacker_applicant.status == StatusEnum.ACCEPTED
        or hacker_applicant.status == StatusEnum.ACCEPTED_INVITE
    ):
        hacker_applicant.status = StatusEnum.SCANNED_IN
        message = f"Welcome {user.first_name}!"
    elif hacker_applicant.status in (
        StatusEnum.WALK_IN,
        StatusEnum.WALK_IN_SUBMITTED,
    ):
        if not application.is_draft:
            hacker_applicant.status = StatusEnum.WALK_IN_SUBMITTED
        message = f"Welcome walk-in {user.first_name}!"
    else:
        message = f"Already scanned in: {user.first_name}!"

    session.add(hacker_applicant)
    session.commit()
    session.refresh(hacker_applicant)

    answers_statement = (
        select(FormAnswer, FormQuestion)
        .join(FormQuestion, FormAnswer.question_id == FormQuestion.question_id)
        .where(FormAnswer.application_id == application_id)
    )
    answers_results = session.exec(answers_statement).all()

    answers_dict = {
        "firstName": user.first_name,
        "lastName": user.last_name,
        "email": user.email,
    }

    label_to_key = {
        QuestionLabel.PHONE_NUMBER.value: "phoneNumber",
        QuestionLabel.DIETARY_RESTRICTIONS.value: "dietaryRestrictions",
        QuestionLabel.T_SHIRT_SIZE.value: "tShirtSize",
    }

    for answer, question in answers_results:
        key = label_to_key.get(question.label, question.label.lower().replace(" ", ""))
        answers_dict[key] = answer.answer

    food_tracking_statement = (
        select(FoodTracking, Meal)
        .join(Meal, FoodTracking.meal_id == Meal.id)
        .where(FoodTracking.user_id == user.uid)
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
        select(func.count(HackathonApplicant.application_id)).where(
            HackathonApplicant.status == StatusEnum.SCANNED_IN
        )
    ).one()

    walkin_count = session.exec(
        select(func.count(HackathonApplicant.application_id)).where(
            col(HackathonApplicant.status).in_(
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
