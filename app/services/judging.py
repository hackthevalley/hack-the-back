import random
import uuid
from datetime import datetime, timedelta, timezone

from sqlmodel import Session, col, select

from app.models.forms import FormApplication, HackathonApplicant, StatusEnum
from app.models.judging import (
    JudgingApplicationScore,
    JudgingDecision,
    JudgingJudgeState,
)
from app.services import crowd_bt

MIN_COMPARISONS = 2
ASSIGNMENT_TIMEOUT_MINUTES = 5
ELIGIBLE_STATUSES = (
    StatusEnum.APPLIED,
    StatusEnum.UNDER_REVIEW,
)


def _eligible_application_ids(session: Session) -> list[uuid.UUID]:
    statement = (
        select(FormApplication.application_id)
        .join(
            HackathonApplicant,
            HackathonApplicant.application_id
            == FormApplication.application_id,
        )
        .where(
            FormApplication.is_draft.is_(False),
            col(HackathonApplicant.status).in_(ELIGIBLE_STATUSES),
        )
    )
    return list(session.exec(statement).all())


def sync_application_scores(session: Session) -> list[JudgingApplicationScore]:
    application_ids = _eligible_application_ids(session)
    if not application_ids:
        return []
    existing = {
        score.application_id: score
        for score in session.exec(
            select(JudgingApplicationScore).where(
                col(JudgingApplicationScore.application_id).in_(application_ids)
            )
        ).all()
    }
    for application_id in application_ids:
        if application_id not in existing:
            score = JudgingApplicationScore(application_id=application_id)
            session.add(score)
            existing[application_id] = score
    session.flush()
    return [existing[application_id] for application_id in application_ids]


def get_or_create_judge_state(
    session: Session, judge_id: uuid.UUID, *, lock: bool = False
) -> JudgingJudgeState:
    statement = select(JudgingJudgeState).where(
        JudgingJudgeState.judge_id == judge_id
    )
    if lock:
        statement = statement.with_for_update()
    state = session.exec(statement).first()
    if state is None:
        state = JudgingJudgeState(judge_id=judge_id)
        session.add(state)
        session.flush()
    return state


def _seen_ids(session: Session, judge_id: uuid.UUID) -> set[uuid.UUID]:
    decisions = session.exec(
        select(JudgingDecision).where(JudgingDecision.judge_id == judge_id)
    ).all()
    return {
        application_id
        for decision in decisions
        for application_id in (
            decision.winner_application_id,
            decision.loser_application_id,
        )
    }


def _busy_ids(session: Session, judge_id: uuid.UUID) -> set[uuid.UUID]:
    cutoff = datetime.now(timezone.utc) - timedelta(
        minutes=ASSIGNMENT_TIMEOUT_MINUTES
    )
    states = session.exec(
        select(JudgingJudgeState).where(
            JudgingJudgeState.judge_id != judge_id,
            JudgingJudgeState.updated_at >= cutoff,
        )
    ).all()
    return {
        application_id
        for state in states
        for application_id in (
            state.left_application_id,
            state.right_application_id,
        )
        if application_id is not None
    }


def assign_pair(
    session: Session, judge_id: uuid.UUID
) -> tuple[JudgingApplicationScore, JudgingApplicationScore] | None:
    scores = sync_application_scores(session)
    score_by_id = {score.application_id: score for score in scores}
    state = get_or_create_judge_state(session, judge_id, lock=True)

    if (
        state.left_application_id in score_by_id
        and state.right_application_id in score_by_id
    ):
        state.updated_at = datetime.now(timezone.utc)
        session.add(state)
        session.commit()
        return (
            score_by_id[state.left_application_id],
            score_by_id[state.right_application_id],
        )

    busy = _busy_ids(session, judge_id)
    seen = _seen_ids(session, judge_id)
    left = score_by_id.get(state.left_application_id)
    available = [score for score in scores if score.application_id not in busy]

    if left is None:
        anchors = [score for score in available if score.application_id not in seen]
        if not anchors:
            anchors = available
        if not anchors:
            return None
        least_compared = min(score.comparison_count for score in anchors)
        left = random.choice(
            [score for score in anchors if score.comparison_count == least_compared]
        )

    candidates = [
        score
        for score in available
        if score.application_id != left.application_id
        and score.application_id not in seen
    ]
    if not candidates:
        return None

    under_sampled = [
        score for score in candidates if score.comparison_count < MIN_COMPARISONS
    ]
    candidates = under_sampled or candidates
    random.shuffle(candidates)
    if random.random() < crowd_bt.EPSILON:
        right = candidates[0]
    else:
        right = max(
            candidates,
            key=lambda score: crowd_bt.expected_information_gain(
                state.alpha,
                state.beta,
                left.mu,
                left.sigma_sq,
                score.mu,
                score.sigma_sq,
            ),
        )

    state.left_application_id = left.application_id
    state.right_application_id = right.application_id
    state.updated_at = datetime.now(timezone.utc)
    session.add(state)
    session.commit()
    session.refresh(left)
    session.refresh(right)
    return left, right


def record_vote(
    session: Session,
    judge_id: uuid.UUID,
    request_id: uuid.UUID,
    left_application_id: uuid.UUID,
    right_application_id: uuid.UUID,
    winner_application_id: uuid.UUID,
) -> tuple[JudgingDecision, JudgingApplicationScore, JudgingApplicationScore, float]:
    # Serialize a judge's submissions before checking idempotency. This makes
    # concurrent retries wait for the first transaction and then reuse it.
    state = get_or_create_judge_state(session, judge_id, lock=True)
    duplicate = session.exec(
        select(JudgingDecision).where(JudgingDecision.request_id == request_id)
    ).first()
    if duplicate is not None:
        if duplicate.judge_id != judge_id:
            raise ValueError("Request ID has already been used by another judge")
        winner = session.get(JudgingApplicationScore, duplicate.winner_application_id)
        loser = session.get(JudgingApplicationScore, duplicate.loser_application_id)
        if winner is None or loser is None:
            raise RuntimeError("Decision references missing score state")
        return duplicate, winner, loser, state.alpha / (state.alpha + state.beta)

    assigned = (state.left_application_id, state.right_application_id)
    submitted = (left_application_id, right_application_id)
    if assigned != submitted:
        raise ValueError("Submitted pair is not the judge's active assignment")
    if winner_application_id not in submitted:
        raise ValueError("Winner must be one of the assigned applications")

    loser_application_id = (
        right_application_id
        if winner_application_id == left_application_id
        else left_application_id
    )
    scores = session.exec(
        select(JudgingApplicationScore)
        .where(
            col(JudgingApplicationScore.application_id).in_(
                [winner_application_id, loser_application_id]
            )
        )
        .with_for_update()
    ).all()
    score_by_id = {score.application_id: score for score in scores}
    winner = score_by_id.get(winner_application_id)
    loser = score_by_id.get(loser_application_id)
    if winner is None or loser is None:
        raise ValueError("Assigned application is not eligible for judging")

    updated = crowd_bt.update(
        state.alpha,
        state.beta,
        winner.mu,
        winner.sigma_sq,
        loser.mu,
        loser.sigma_sq,
    )
    now = datetime.now(timezone.utc)
    state.alpha = updated.alpha
    state.beta = updated.beta
    state.left_application_id = right_application_id
    state.right_application_id = None
    state.updated_at = now
    winner.mu = updated.winner_mu
    winner.sigma_sq = updated.winner_sigma_sq
    winner.comparison_count += 1
    winner.updated_at = now
    loser.mu = updated.loser_mu
    loser.sigma_sq = updated.loser_sigma_sq
    loser.comparison_count += 1
    loser.updated_at = now
    decision = JudgingDecision(
        request_id=request_id,
        judge_id=judge_id,
        winner_application_id=winner_application_id,
        loser_application_id=loser_application_id,
    )
    session.add_all([state, winner, loser, decision])
    session.commit()
    session.refresh(decision)
    return decision, winner, loser, state.alpha / (state.alpha + state.beta)
