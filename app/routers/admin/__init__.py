from fastapi import APIRouter

from app.routers.admin.account import router as account

router = APIRouter()

router.include_router(account, prefix="/account")
