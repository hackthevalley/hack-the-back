from typing import List
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlmodel import select

from app.core.db import SessionDep
from app.models.meal import Meal

router = APIRouter()


class FoodItem(BaseModel):
    id: str
    name: str
    day: int
    serving: bool


class FoodResponse(BaseModel):
    allFood: List[FoodItem]
    currentMeal: str | None


def get_day_number(day_str: str) -> int:
    """Convert day string to number (friday=1, saturday=2, sunday=3)"""
    day_map = {
        "friday": 1,
        "saturday": 2,
        "sunday": 3,
    }
    return day_map.get(day_str.lower(), 0)


@router.get("", response_model=FoodResponse)
async def get_food_data(session: SessionDep):
    """
    Get all meals with indication of which one is currently being served
    """
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
async def track_food(request: dict, session: SessionDep):
    """
    Track food items for a hacker
    """
    from app.models.food_tracking import Food_Tracking
    from app.models.forms import Forms_Application

    food_items = request.get("food", [])

    if not food_items:
        return {"message": "No food items to track"}

    application_ids = [UUID(item["application"]) for item in food_items]
    meal_ids = [UUID(item["serving"]) for item in food_items]

    app_statement = select(Forms_Application).where(
        Forms_Application.application_id.in_(application_ids)
    )
    applications = session.exec(app_statement).all()

    app_map = {str(app.application_id): app for app in applications}

    for item in food_items:
        if item["application"] not in app_map:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Application not found: {item['application']}",
            )

    tracking_pairs = []
    for item in food_items:
        application = app_map[item["application"]]
        meal_id = UUID(item["serving"])
        tracking_pairs.append((application.uid, meal_id))

    user_ids = [pair[0] for pair in tracking_pairs]
    existing_statement = select(Food_Tracking).where(
        Food_Tracking.user_id.in_(user_ids), Food_Tracking.meal_id.in_(meal_ids)
    )
    existing_trackings = session.exec(existing_statement).all()

    existing_pairs = {
        (str(tracking.user_id), str(tracking.meal_id))
        for tracking in existing_trackings
    }

    new_trackings = []
    for user_id, meal_id in tracking_pairs:
        if (str(user_id), str(meal_id)) not in existing_pairs:
            new_trackings.append(
                Food_Tracking(
                    user_id=user_id,
                    meal_id=meal_id,
                )
            )

    try:
        if new_trackings:
            session.add_all(new_trackings)
        session.commit()
    except Exception as e:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to track food: {str(e)}",
        )

    return {
        "message": "Food tracking updated successfully",
        "new_records_created": len(new_trackings),
    }
