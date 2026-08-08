import logging
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.dialects.postgresql import insert
from sqlmodel import col, select

from app.core.db import SessionDep
from app.models.meal import Meal

router = APIRouter()
logger = logging.getLogger(__name__)


class FoodItem(BaseModel):
    id: str
    name: str
    day: int
    serving: bool


class FoodResponse(BaseModel):
    all_food: list[FoodItem] = Field(alias="allFood")
    current_meal: str | None = Field(alias="currentMeal")


class FoodTrackingItem(BaseModel):
    application: UUID
    serving: UUID


class FoodTrackingRequest(BaseModel):
    food: list[FoodTrackingItem] = Field(
        max_length=100, description="List of food items to track (max 100 per request)"
    )


def get_day_number(day_str: str) -> int:
    day_map = {"friday": 1, "saturday": 2, "sunday": 3}
    day_number = day_map.get(day_str.lower())
    if day_number is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Meal has invalid day: {day_str}",
        )
    return day_number


@router.get("", response_model=FoodResponse)
def get_food_data(session: SessionDep):
    statement = select(Meal)
    meals = session.exec(statement).all()

    all_food = []
    current_meal = None

    for meal in meals:
        day_num = get_day_number(meal.day.value)
        food_item = FoodItem(
            id=str(meal.id),
            name=meal.meal_type.value.capitalize(),
            day=day_num,
            serving=meal.is_active,
        )
        all_food.append(food_item)

        if meal.is_active:
            current_meal = f"Day {day_num} {meal.meal_type.value.capitalize()}"

    return FoodResponse(allFood=all_food, currentMeal=current_meal)


@router.post("/tracking")
def track_food(request: FoodTrackingRequest, session: SessionDep):
    from app.models.food_tracking import FoodTracking
    from app.models.forms import FormApplication

    food_items = request.food

    if not food_items:
        return {"message": "No food items to track"}

    application_ids = [item.application for item in food_items]

    app_statement = select(FormApplication).where(
        col(FormApplication.application_id).in_(application_ids)
    )
    applications = session.exec(app_statement).all()

    app_map = {app.application_id: app for app in applications}

    for item in food_items:
        if item.application not in app_map:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Application not found: {item.application}",
            )

    tracking_pairs = []
    for item in food_items:
        application = app_map[item.application]
        meal_id = item.serving
        tracking_pairs.append((application.uid, meal_id))

    unique_pairs = set(tracking_pairs)

    try:
        inserted_ids = session.exec(
            insert(FoodTracking)
            .values(
                [
                    {"user_id": user_id, "meal_id": meal_id}
                    for user_id, meal_id in unique_pairs
                ]
            )
            .on_conflict_do_nothing(constraint="uq_food_tracking_user_meal")
            .returning(FoodTracking.id)
        ).all()
        session.commit()
    except Exception as error:
        session.rollback()
        logger.exception(
            "Failed to track food for %s unique check-ins", len(unique_pairs)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to track food",
        ) from error

    return {
        "message": "Food tracking updated successfully",
        "new_records_created": len(inserted_ids),
    }
