# app/routers/points.py

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select, func
from app.models.qr_scanner import Event, Scan
from typing import Annotated, List

from app.core.db import SessionDep
from app.models.user import Account_User
from app.utils import get_current_user

router = APIRouter()


@router.post("/generate_event", response_model=Event)
async def generate_event(
    name: str,
    session: SessionDep,
    current_user: Annotated[Account_User, Depends(get_current_user)],
):
    """
    Create a new Event and return its QR token.
    (In production you'd restrict this to team‐admins.)
    """
    event = Event(name=name)
    session.add(event)
    session.commit()
    session.refresh(event)
    return event


@router.get("/events", response_model=List[Event])
async def list_events(session: SessionDep):
    """List all hackathon events (and their QR tokens)."""
    statement = select(Event)
    return session.exec(statement).all()


@router.post("/scan")
async def scan_event(
    token: str,
    session: SessionDep,
    current_user: Annotated[Account_User, Depends(get_current_user)],
):
    """
    Record a scan for the current hacker.
    Each (hacker_id, event_id) is unique, so re‐scans don't grant more points.
    """
    # 1. Find event by token
    statement = select(Event).where(Event.token == token)
    event = session.exec(statement).first()
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    # 2. Check if already scanned
    exists = session.exec(
        select(Scan)
        .where(Scan.hacker_id == current_user.id)
        .where(Scan.event_id == event.id)
    ).first()
    if exists:
        return {"detail": "Already scanned", "points": await _get_points(session, current_user.id)}

    # 3. Record new scan
    scan = Scan(hacker_id=current_user.id, event_id=event.id)
    session.add(scan)
    session.commit()

    points = await _get_points(session, current_user.id)
    return {"detail": "Scan recorded", "points": points}


async def _get_points(session: SessionDep, hacker_id: int) -> int:
    """Helper to count distinct scans for a hacker."""
    count = session.exec(
        select(func.count())
        .select_from(Scan)
        .where(Scan.hacker_id == hacker_id)
    ).one()
    return count


@router.get("/my_points")
async def my_points(
    session: SessionDep,
    current_user: Annotated[Account_User, Depends(get_current_user)],
):
    """
    Return your total points and list of event names you've scanned.
    """
    total = await _get_points(session, current_user.id)
    scans = session.exec(
        select(Event.name)
        .join(Scan, Scan.event_id == Event.id)
        .where(Scan.hacker_id == current_user.id)
    ).all()
    return {"points": total, "scanned_events": scans}


@router.get("/leaderboard")
async def leaderboard(
    session: SessionDep,  # Required parameter comes first
    limit: int = 10,      # Optional parameter with default value comes second
):
    """
    Top‐N hackers by scanned events.
    """
    # Rest of the function remains the same
    results = session.exec(
        select(
            Account_User.username,
            func.count(Scan.id).label("points")
        )
        .join(Scan, Scan.hacker_id == Account_User.id)
        .group_by(Account_User.username)
        .order_by(func.count(Scan.id).desc())
        .limit(limit)
    ).all()
    return [{"username": r[0], "points": r[1]} for r in results]