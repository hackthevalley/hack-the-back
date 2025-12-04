import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session

from app.config import validate_config
from app.core.db import (
    create_db_and_tables,
    engine,
    seed_form_time,
    seed_meals,
    seed_questions,
)
from app.models.meal import MealType, WeekDay
from app.routers import router


def load_form_questions() -> list[dict]:
    """Load form questions from JSON configuration file."""
    questions_path = Path(__file__).parent / "data" / "form_questions.json"
    with open(questions_path, "r", encoding="utf-8") as f:
        return json.load(f)


meals = [
    {"day": WeekDay.FRIDAY, "meal_type": MealType.DINNER, "is_active": False},
    {"day": WeekDay.SATURDAY, "meal_type": MealType.BREAKFAST, "is_active": False},
    {"day": WeekDay.SATURDAY, "meal_type": MealType.LUNCH, "is_active": False},
    {"day": WeekDay.SATURDAY, "meal_type": MealType.DINNER, "is_active": False},
    {"day": WeekDay.SUNDAY, "meal_type": MealType.BREAKFAST, "is_active": False},
    {"day": WeekDay.SUNDAY, "meal_type": MealType.LUNCH, "is_active": False},
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    validate_config()

    create_db_and_tables()

    questions = load_form_questions()
    with Session(engine) as session:
        seed_questions(questions, session)
        seed_form_time(session)
        seed_meals(meals, session)
    yield


def get_application():
    app = FastAPI(lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(router, prefix="/api")

    return app


app = get_application()


@app.get("/")
async def read_root():
    return {"Hello": "World"}
