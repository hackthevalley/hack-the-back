import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlmodel import Session, select
from starlette.concurrency import run_in_threadpool

from app.core.db import engine
from app.core.errors import ServiceError
from app.models.constants import TokenScope, UserRole
from app.models.user import AccountUser
from app.services.check_in_live import check_in_connections
from app.services.tokens import decode_token

router = APIRouter()


def authorize_staff(token: str) -> bool:
    token_data = decode_token(token)
    with Session(engine) as session:
        user = session.exec(
            select(AccountUser).where(AccountUser.email == token_data.email)
        ).first()
        return bool(
            user
            and user.is_active
            and user.token_version == token_data.token_version
            and user.role in (UserRole.ADMIN, UserRole.VOLUNTEER)
            and TokenScope.RESET_PASSWORD.value not in token_data.scopes
            and TokenScope.ACCOUNT_ACTIVATE.value not in token_data.scopes
        )


@router.websocket("/live")
async def live_check_in_counts(websocket: WebSocket) -> None:
    await websocket.accept()
    connected = False
    try:
        while True:
            payload = await asyncio.wait_for(websocket.receive_json(), timeout=45)
            token = payload.get("token") if isinstance(payload, dict) else None
            if not isinstance(token, str) or not await run_in_threadpool(
                authorize_staff, token
            ):
                await websocket.close(code=1008)
                return
            if not connected:
                await check_in_connections.add(websocket)
                connected = True
    except WebSocketDisconnect:
        pass
    except (TimeoutError, ValueError, ServiceError):
        await websocket.close(code=1008)
    finally:
        check_in_connections.remove(websocket)

