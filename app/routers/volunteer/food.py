from typing import List
from uuid import UUID

from fastapi import APIRouter, HTTPException
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
    # Get all meals
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

    # Track each food item
    for item in food_items:
        application_id = UUID(item["application"])
        meal_id = UUID(item["serving"])

        # Get the user from application
        app_statement = select(Forms_Application).where(
            Forms_Application.application_id == application_id
        )
        application = session.exec(app_statement).first()

        if not application:
            raise HTTPException(status_code=404, detail="Application not found")

        # Check if this tracking already exists
        existing_statement = select(Food_Tracking).where(
            Food_Tracking.user_id == application.uid,
            Food_Tracking.meal_id == meal_id,
        )
        existing_tracking = session.exec(existing_statement).first()

        if not existing_tracking:
            # Create new food tracking
            new_tracking = Food_Tracking(
                user_id=application.uid,
                meal_id=meal_id,
            )
            session.add(new_tracking)

    session.commit()

    return {"message": "Food tracking updated successfully"}
