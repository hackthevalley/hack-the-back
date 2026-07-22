import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session
from starlette.concurrency import run_in_threadpool

from app.config import AppConfig, validate_config
from app.core.db import (
    ADVISORY_LOCK_DATABASE_INIT,
    advisory_lock,
    engine,
    seed_form_time,
    seed_meals,
    seed_questions,
)
from app.models.meal import MealType, WeekDay
from app.routers import router


def load_form_questions() -> list[dict]:
    questions_path = Path(__file__).parent / "data" / "form_questions.json"
    with open(questions_path, encoding="utf-8") as f:
        content = f.read()
        return json.loads(content)


meals = [
    {"day": WeekDay.FRIDAY, "meal_type": MealType.DINNER, "is_active": False},
    {"day": WeekDay.SATURDAY, "meal_type": MealType.BREAKFAST, "is_active": False},
    {"day": WeekDay.SATURDAY, "meal_type": MealType.LUNCH, "is_active": False},
    {"day": WeekDay.SATURDAY, "meal_type": MealType.DINNER, "is_active": False},
    {"day": WeekDay.SUNDAY, "meal_type": MealType.BREAKFAST, "is_active": False},
    {"day": WeekDay.SUNDAY, "meal_type": MealType.LUNCH, "is_active": False},
]


def initialize_database():
    validate_config()
    questions = load_form_questions()
    with Session(engine) as session:
        # Every Uvicorn worker executes its lifespan. Serialize schema creation
        # and seeding so concurrent workers cannot race while seeding defaults.
        with advisory_lock(session, ADVISORY_LOCK_DATABASE_INIT):
            seed_questions(questions, session)
            seed_form_time(session)
            seed_meals(meals, session)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await run_in_threadpool(initialize_database)
    yield


def get_application():
    docs_url = "/docs" if AppConfig.ENABLE_API_DOCS else None
    redoc_url = "/redoc" if AppConfig.ENABLE_API_DOCS else None
    openapi_url = "/openapi.json" if AppConfig.ENABLE_API_DOCS else None
    app = FastAPI(
        lifespan=lifespan,
        docs_url=docs_url,
        redoc_url=redoc_url,
        openapi_url=openapi_url,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=AppConfig.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(router, prefix="/api")

    return app


app = get_application()


@app.get("/")
def read_root():
    return {"Hello": "World"}
