from contextlib import nullcontext

from sqlmodel import Session, SQLModel, create_engine, select

from app.core import db
from app.models.meal import Meal, MealType, WeekDay


def test_meal_seed_repairs_missing_rows_without_duplicates(monkeypatch):
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(db, "advisory_lock", lambda *_args: nullcontext())
    meals = [
        {"day": WeekDay.FRIDAY, "meal_type": MealType.DINNER},
        {"day": WeekDay.SATURDAY, "meal_type": MealType.BREAKFAST},
    ]

    with Session(engine) as session:
        session.add(Meal(day=WeekDay.FRIDAY, meal_type=MealType.DINNER))
        session.commit()

        db.seed_meals(meals, session)
        db.seed_meals(meals, session)

        assert len(session.exec(select(Meal)).all()) == 2

    engine.dispose()
