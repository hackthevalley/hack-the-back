from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session

from app.core.db import (
    create_db_and_tables,
    engine,
    seed_form_time,
    seed_meals,
    seed_questions,
)
from app.models.meal import MealType, WeekDay
from app.routers import router

questions = [
    {"label": "First Name", "required": True},
    {"label": "Last Name", "required": True},
    {"label": "Email", "required": True},
    {"label": "Phone Number", "required": True},
    {"label": "Country", "required": True},
    {"label": "School Name", "required": True},
    {"label": "Major", "required": True},
    {"label": "Current Level of Study", "required": True},
    {"label": "Expected Graduation Year", "required": True},
    {"label": "Age", "required": True},
    {"label": "Gender", "required": True},
    {"label": "Race/Ethnicity", "required": True},
    {"label": "Part of the LGBTQ+ Community", "required": True},
    {"label": "Person with Disabilities?", "required": True},
    {"label": "Hackathon Count?", "required": True},
    {"label": "Github", "required": False},
    {"label": "LinkedIn", "required": False},
    {"label": "Portfolio", "required": False},
    {"label": "Attach Your Resume", "required": True},
    {"label": "UI/UX Design", "required": False},
    {"label": "Frontend Development", "required": False},
    {"label": "Backend Development", "required": False},
    {"label": "Fullstack Development", "required": False},
    {"label": "Project Management", "required": False},
    {"label": "Web, Crypto, Blockchain", "required": False},
    {"label": "Cybersecurity", "required": False},
    {"label": "Machine Learning", "required": False},
    {"label": "Dietary Restrictions", "required": True},
    {"label": "T-Shirt Size", "required": True},
    {"label": "MLH Code of Conduct", "required": True},
    {"label": "MLH Privacy Policy, MLH Contest Terms and Conditions", "required": True},
    {"label": "MLH Event Communication", "required": False},
    {"label": "Hack the Valley Consent Form Agreement", "required": True},
]

meals = [
    {"day": WeekDay.FRIDAY, "meal_type": MealType.DINNER, "is_active": False},
    # {"day": WeekDay.FRIDAY, "meal_type": MealType.MERCH, "is_active": False},
    {"day": WeekDay.SATURDAY, "meal_type": MealType.BREAKFAST, "is_active": False},
    {"day": WeekDay.SATURDAY, "meal_type": MealType.LUNCH, "is_active": False},
    {"day": WeekDay.SATURDAY, "meal_type": MealType.DINNER, "is_active": False},
    {"day": WeekDay.SUNDAY, "meal_type": MealType.BREAKFAST, "is_active": False},
    {"day": WeekDay.SUNDAY, "meal_type": MealType.LUNCH, "is_active": False},
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
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
