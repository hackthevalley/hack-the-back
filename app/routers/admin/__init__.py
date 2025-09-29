from fastapi import APIRouter

from app.routers.admin.account import router as account
from app.routers.admin.forms import router as forms
from app.routers.admin.food_tracking import router as foodtracker  # Fixed: food_tracking not foodtracker

router = APIRouter()

router.include_router(account, prefix="/account")
router.include_router(forms, prefix="/forms")
router.include_router(foodtracker, prefix="/foodtracker")