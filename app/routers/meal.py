
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session, select

from app.core.db import SessionDep

from app.models.meal import (
    Meal,
    MealCreate,
    MealRead,
    MealUpdate,
    WeekDay,
    MealType
)

router = APIRouter()

@router.post("", response_model=MealRead, status_code=status.HTTP_201_CREATED)
async def createmeal(*, session: SessionDep, meal: MealCreate):
    query = select(Meal).where(
        Meal.day == meal.day,
        Meal.meal_type == meal.meal_type
    )
    existing_meal = session.exec(query).first()
    if existing_meal and meal.meal_type!="snack":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Meal for {existing_meal.name} already exists"
        )
    
    db_meal = Meal.from_orm(meal)

    session.add(db_meal)
    session.commit()
    session.refresh(db_meal)
    
    response = MealRead.from_orm(db_meal)
    response.name = db_meal.name
    return response

@router.get("", response_model=List[MealRead])
def getmeals(*,
              session: SessionDep,
              day: Optional[WeekDay] = None,
              meal_type: Optional[MealType] = None,
              is_active: Optional[bool] = Query(default=None)):

    query = select(Meal)

    if day is not None:
        query = query.where(Meal.day == day)
    if meal_type is not None:
        query = query.where(Meal.meal_type == meal_type)
    if is_active is not None:
        query = query.where(Meal.is_active == is_active)

    db_meals = session.exec(query).all()

    results = []
    for meal in db_meals:
        meal_read = MealRead.from_orm(meal)
        meal_read.name = meal.name
        results.append(meal_read)
    
    return results

@router.get("/{meal_id}", response_model=MealRead)
def getmeal(*, 
             session: SessionDep,
             meal_id: UUID):
    
    meal = session.get(Meal, meal_id)
    if not meal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meal not found"
        )

    response = MealRead.from_orm(meal)
    response.name = meal.name
    return response

@router.patch("/{meal_id}", response_model=MealRead)
def updatemeal(*,
                session: SessionDep,
                meal_id: UUID,
                meal_update: MealUpdate):
    db_meal = session.get(Meal, meal_id)
    if not db_meal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meal not found"
        )
    meal_data = meal_update.dict(exclude_unset=True)
    for key, value in meal_data.items():
        setattr(db_meal, key, value)
    
    session.add(db_meal)
    session.commit()
    session.refresh(db_meal)

    response = MealRead.from_orm(db_meal)
    response.name = db_meal.name
    return response

@router.delete("/{meal_id}", status_code=status.HTTP_204_NO_CONTENT)
def deletemeal(meal_id: UUID, session: SessionDep):
    meal = session.get(Meal, meal_id)
    if not meal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meal not found"
        )
    
    session.delete(meal)
    session.commit()
