from fastapi import APIRouter

from app.routers.volunteer.food import router as food
from app.routers.volunteer.forms import router as forms
from app.routers.volunteer.qr import router as qr

router = APIRouter()

router.include_router(food, prefix="/food")
router.include_router(qr, prefix="/check-ins")
router.include_router(forms, prefix="/forms")
