from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Security, status

from app.models.constants import TokenScope
from app.models.token import TokenData
from app.routers.account import router as account
from app.routers.admin import router as admin
from app.routers.forms import router as forms
from app.routers.meal import router as meal
from app.routers.volunteer import router as volunteer
from app.utils import decode_jwt

router = APIRouter()


def is_admin(
    token_data: Annotated[
        TokenData, Security(decode_jwt, scopes=[TokenScope.ADMIN.value])
    ],
) -> bool:
    if TokenScope.ADMIN.value not in token_data.scopes:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User does not have permission",
        )
    return True


def is_volunteer(
    token_data: Annotated[TokenData, Security(decode_jwt)],
) -> bool:
    if (
        TokenScope.ADMIN.value not in token_data.scopes
        and TokenScope.VOLUNTEER.value not in token_data.scopes
    ):
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
router.include_router(meal, prefix="/meals", tags=["meals"])
router.include_router(
    volunteer,
    prefix="/volunteer",
    tags=["volunteer"],
    dependencies=[Depends(is_volunteer)],
)
