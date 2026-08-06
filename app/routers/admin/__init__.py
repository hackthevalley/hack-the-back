from fastapi import APIRouter

from app.routers.admin.account import router as account
from app.routers.admin.forms import router as forms
from app.routers.admin.judging import router as judging

router = APIRouter()

router.include_router(account, prefix="/account")
router.include_router(forms, prefix="/forms")
router.include_router(judging, prefix="/judging")
