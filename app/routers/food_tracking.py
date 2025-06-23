from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlmodel import select

from app.core.db import SessionDep
from app.models.food_tracking import (
    Food_Tracking,
    Food_TrackingCreate,
    Food_TrackingRead,
)
from app.models.meal import Meal
from app.models.user import Account_User

router = APIRouter()


@router.post(
    "/checkin", response_model=Food_TrackingRead, status_code=status.HTTP_201_CREATED
)
def checkin(*, session: SessionDep, food_tracking: Food_TrackingCreate):
    user = session.get(Account_User, food_tracking.user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    meal = session.get(Meal, food_tracking.meal_id)
    if not meal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Meal not found"
        )

    if not meal.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Meal '{meal.name}' is not active",
        )

    query = select(Food_Tracking).where(
        Food_Tracking.user_id == food_tracking.user_id,
        Food_Tracking.meal_id == food_tracking.meal_id,
    )
    existing_tracking = session.exec(query).first()
    if existing_tracking:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"User has already grabbed {meal.name}",
        )

    db_food_tracking = Food_Tracking.from_orm(food_tracking)
    session.add(db_food_tracking)
    session.commit()
    session.refresh(db_food_tracking)

    response = Food_TrackingRead.from_orm(db_food_tracking)
    response.name = meal.name
    return response


@router.get("/getrecords", response_model=List[Food_TrackingRead])
def getrecords(
    *,
    session: SessionDep,
    user_id: Optional[UUID] = None,
    meal_id: Optional[UUID] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: Optional[int] = 100,
):
    query = select(Food_Tracking, Meal).join(Meal)

    if user_id is not None:
        query = query.where(Food_Tracking.user_id == user_id)
    if meal_id is not None:
        query = query.where(Food_Tracking.meal_id == meal_id)
    if start_date is not None:
        query = query.where(Food_Tracking.grabbed_at >= start_date)
    if end_date is not None:
        query = query.where(Food_Tracking.grabbed_at <= end_date)

    results = session.exec(query.limit(limit)).all()

    tracking_records = []
    for tracking, meal in results:
        tracking_read = Food_TrackingRead.from_orm(tracking)
        tracking_read.name = meal.name
        tracking_records.append(tracking_read)

    return tracking_records


@router.get("/getmeals/{user_id}", response_model=List[Food_TrackingRead])
def getmeals(*, session: SessionDep, user_id: UUID, limit: int = 100):
    user = session.get(Account_User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    query = (
        select(Food_Tracking, Meal).join(Meal).where(Food_Tracking.user_id == user_id)
    )

    results = session.exec(query.limit(limit)).all()
    if not results:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Food tracking record not found",
        )

    tracking_records = []
    for tracking, meal in results:
        tracking_read = Food_TrackingRead.from_orm(tracking)
        tracking_read.name = meal.name
        tracking_records.append(tracking_read)

    return tracking_records


@router.get("/getusers/{meal_id}", response_model=List[Food_TrackingRead])
def getusers(*, session: SessionDep, meal_id: UUID, limit: int = 100):
    query = (
        select(Food_Tracking, Meal).join(Meal).where(Food_Tracking.meal_id == meal_id)
    )

    results = session.exec(query.limit(limit)).all()
    if not results:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Food tracking record not found",
        )

    tracking_records = []
    for tracking, meal in results:
        tracking_read = Food_TrackingRead.from_orm(tracking)
        tracking_read.name = meal.name
        tracking_records.append(tracking_read)

    return tracking_records


@router.get("/get/{tracking_id}", response_model=Food_TrackingRead)
def gettracking(*, session: SessionDep, tracking_id: UUID):
    query = select(Food_Tracking, Meal).where(Food_Tracking.id == tracking_id)

    result = session.exec(query).first()
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Food tracking record not found",
        )

    tracking, meal = result

    session.add(tracking)
    session.commit()
    session.refresh(tracking)

    tracking_read = Food_TrackingRead.from_orm(tracking)
    tracking_read.name = meal.name

    return tracking_read


@router.delete("/{tracking_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_food_tracking(*, session: SessionDep, tracking_id: UUID):
    tracking = session.get(Food_Tracking, tracking_id)
    if not tracking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Food tracking record not found",
        )

    session.delete(tracking)
    session.commit()
