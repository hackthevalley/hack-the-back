from fastapi import APIRouter

from app.routers.admin.account import router as account
from app.routers.admin.food import router as food
from app.routers.admin.forms import router as forms
from app.routers.admin.qr import router as qr

router = APIRouter()

router.include_router(account, prefix="/account")
router.include_router(forms, prefix="/forms")
router.include_router(qr, prefix="/qr")
router.include_router(food, prefix="/food")
