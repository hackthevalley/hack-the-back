from fastapi import APIRouter

from app.routers.admin.account import router as account
from app.routers.admin.forms import router as forms

router = APIRouter()

router.include_router(account, prefix="/account")
router.include_router(forms, prefix="/forms")
