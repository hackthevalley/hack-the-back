import asyncio

from fastapi import WebSocket, WebSocketDisconnect
from sqlmodel import Session, col, func, select
from starlette.concurrency import run_in_threadpool

from app.core.db import engine
from app.models.forms import HackathonApplicant, StatusEnum


def get_check_in_counts(session: Session) -> dict[str, int]:
    scanned_count = session.exec(
        select(func.count(HackathonApplicant.application_id)).where(
            HackathonApplicant.status == StatusEnum.SCANNED_IN
        )
    ).one()
    walkin_count = session.exec(
        select(func.count(HackathonApplicant.application_id)).where(
            col(HackathonApplicant.status).in_(
                [StatusEnum.WALK_IN, StatusEnum.WALK_IN_SUBMITTED]
            )
        )
    ).one()
    return {"scannedCount": scanned_count, "walkinCount": walkin_count}


def load_check_in_counts() -> dict[str, int]:
    with Session(engine) as session:
        return get_check_in_counts(session)


class CheckInConnections:
    def __init__(self) -> None:
        self.connections: set[WebSocket] = set()
        self.lock = asyncio.Lock()

    async def add(self, websocket: WebSocket) -> None:
        async with self.lock:
            self.connections.add(websocket)
            counts = await run_in_threadpool(load_check_in_counts)
            await websocket.send_json(counts)

    def remove(self, websocket: WebSocket) -> None:
        self.connections.discard(websocket)

    async def broadcast(self) -> None:
        async with self.lock:
            counts = await run_in_threadpool(load_check_in_counts)
            for websocket in list(self.connections):
                try:
                    await websocket.send_json(counts)
                except (RuntimeError, WebSocketDisconnect):
                    self.remove(websocket)


check_in_connections = CheckInConnections()

