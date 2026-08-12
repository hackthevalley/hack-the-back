from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlmodel import col, select

from app.core.db import SessionDep
from app.models.judging import (
    JudgingApplicationScore,
)
from app.models.user import AccountUser
from app.schemas.judging import (
    JudgingDecisionResponse,
    JudgingPairResponse,
    JudgingRankingEntry,
    JudgingScorePublic,
    JudgingVoteRequest,
)
from app.dependencies.auth import get_current_user
from app.services.judging import ELIGIBLE_STATUSES, assign_pair, record_vote
from app.models.forms import FormApplication, HackathonApplicant

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
    score_mu = func.coalesce(JudgingApplicationScore.mu, 0.0)
    scores = session.exec(
        select(
            FormApplication.application_id,
            score_mu,
            func.coalesce(JudgingApplicationScore.sigma_sq, 1.0),
            func.coalesce(JudgingApplicationScore.comparison_count, 0),
        )
        .outerjoin(
            JudgingApplicationScore,
            JudgingApplicationScore.application_id == FormApplication.application_id,
        )
        .join(
            HackathonApplicant,
            HackathonApplicant.application_id == FormApplication.application_id,
        )
        .where(
            FormApplication.is_draft.is_(False),
            col(HackathonApplicant.status).in_(ELIGIBLE_STATUSES),
        )
        .order_by(
            score_mu.desc(),
            col(FormApplication.application_id),
        )
        .offset(offset)
        .limit(limit)
    ).all()
    return [
        JudgingRankingEntry(
            rank=offset + index + 1,
            application_id=score[0],
            mu=score[1],
            sigma_sq=score[2],
            comparison_count=score[3],
        )
        for index, score in enumerate(scores)
    ]
