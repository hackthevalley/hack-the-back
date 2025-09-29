from typing import List
from uuid import UUID
from fastapi import APIRouter, HTTPException, status
from sqlmodel import select, SQLModel

from app.core.db import SessionDep
from app.models.food_tracking import Food_Tracking, Food_TrackingCreate
from app.models.user import Account_User
from app.models.meal import Meal

router = APIRouter()

class FoodTrackerRequest(SQLModel):
    food: List[dict]  # [{"application": "user_id", "serving": "meal_id"}]

@router.post("/foodtracker", status_code=status.HTTP_200_OK)
def update_food_tracking(*, session: SessionDep, request: FoodTrackerRequest):
    """Create food tracking records for selected meals"""
    created_count = 0
    
    for item in request.food:
        user_id = item["application"]
        meal_id = item["serving"]
        
        # Validate user exists
        user = session.get(Account_User, user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail=f"User {user_id} not found"
            )
        
        # Validate meal exists
        meal = session.get(Meal, meal_id)
        if not meal:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail=f"Meal {meal_id} not found"
            )
        
        # Check if tracking already exists
        existing = session.exec(
            select(Food_Tracking).where(
                Food_Tracking.user_id == user_id,
                Food_Tracking.meal_id == meal_id
            )
        ).first()
        
        if not existing:
            # Create new tracking record
            tracking = Food_TrackingCreate(
                user_id=user_id,
                meal_id=meal_id
            )
            db_tracking = Food_Tracking.from_orm(tracking)
            session.add(db_tracking)
            created_count += 1
    
    session.commit()
    return {"message": f"Created {created_count} food tracking records"}