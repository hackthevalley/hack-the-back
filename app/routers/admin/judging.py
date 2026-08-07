from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import col, select

from app.core.db import SessionDep
from app.models.judging import (
    JudgingApplicationScore,
    JudgingDecisionResponse,
    JudgingPairResponse,
    JudgingRankingEntry,
    JudgingScorePublic,
    JudgingVoteRequest,
)
from app.models.user import AccountUser
from app.services.auth import get_current_user
from app.services.judging import assign_pair, record_vote, sync_application_scores

router = APIRouter()


@router.get("/pair", response_model=JudgingPairResponse)
def get_pair(
    session: SessionDep,
    current_user: Annotated[AccountUser, Depends(get_current_user)],
) -> JudgingPairResponse:
    pair = assign_pair(session, current_user.uid)
    if pair is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No eligible application comparison is available",
        )
    return JudgingPairResponse(left=pair[0], right=pair[1])


@router.post("/decisions", response_model=JudgingDecisionResponse)
def submit_decision(
    vote: JudgingVoteRequest,
    session: SessionDep,
    current_user: Annotated[AccountUser, Depends(get_current_user)],
) -> JudgingDecisionResponse:
    try:
        decision, winner, loser, reliability = record_vote(
            session,
            current_user.uid,
            vote.request_id,
            vote.left_application_id,
            vote.right_application_id,
            vote.winner_application_id,
        )
    except ValueError as error:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(error)
        ) from error
    return JudgingDecisionResponse(
        decision_id=decision.decision_id,
        request_id=decision.request_id,
        winner_application_id=decision.winner_application_id,
        loser_application_id=decision.loser_application_id,
        winner_score=JudgingScorePublic.model_validate(winner),
        loser_score=JudgingScorePublic.model_validate(loser),
        judge_reliability=reliability,
    )


@router.get("/rankings", response_model=list[JudgingRankingEntry])
def get_rankings(
    session: SessionDep,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[JudgingRankingEntry]:
    eligible_scores = sync_application_scores(session)
    session.commit()
    eligible_ids = [score.application_id for score in eligible_scores]
    if not eligible_ids:
        return []
    scores = session.exec(
        select(JudgingApplicationScore)
        .where(col(JudgingApplicationScore.application_id).in_(eligible_ids))
        .order_by(
            col(JudgingApplicationScore.mu).desc(),
            col(JudgingApplicationScore.application_id),
        )
        .offset(offset)
        .limit(limit)
    ).all()
    return [
        JudgingRankingEntry(
            rank=offset + index + 1,
            **JudgingScorePublic.model_validate(score).model_dump(),
        )
        for index, score in enumerate(scores)
    ]
