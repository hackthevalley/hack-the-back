from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.models.constants import UserRole
from app.models.user import Account_User
from app.routers.account import router as account
from app.routers.admin import router as admin
from app.routers.forms import router as forms
from app.routers.meal import router as meal
from app.routers.volunteer import router as volunteer
from app.services.auth import get_current_user

router = APIRouter()


def is_admin(
    current_user: Annotated[Account_User, Depends(get_current_user)],
) -> bool:
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User does not have permission",
        )
    return True


def is_volunteer(
    current_user: Annotated[Account_User, Depends(get_current_user)],
) -> bool:
    if current_user.role not in (UserRole.ADMIN, UserRole.VOLUNTEER):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User does not have permission",
        )
    return True


router.include_router(account, prefix="/account", tags=["account"])
router.include_router(forms, prefix="/forms", tags=["forms"])
router.include_router(
    admin, prefix="/admin", tags=["admin"], dependencies=[Depends(is_admin)]
)
router.include_router(
    meal, prefix="/meals", tags=["meals"], dependencies=[Depends(is_admin)]
)
router.include_router(
    volunteer,
    prefix="/volunteer",
    tags=["volunteer"],
    dependencies=[Depends(is_volunteer)],
)
