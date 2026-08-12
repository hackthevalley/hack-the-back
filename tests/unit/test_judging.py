import importlib
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from app.models.judging import (
    JudgingApplicationScore,
    JudgingDecision,
    JudgingJudgeState,
)
from app.schemas.judging import JudgingVoteRequest
from app.services import judging

judging_router = importlib.import_module("app.routers.admin.judging")


def result(*, all_values=(), first=None):
    value = MagicMock()
    value.all.return_value = list(all_values)
    value.first.return_value = first
    return value


def score(application_id=None, *, comparisons=0, mu=0.0):
    return JudgingApplicationScore(
        application_id=application_id or uuid.uuid4(),
        comparison_count=comparisons,
        mu=mu,
    )


def test_sync_application_scores_handles_empty_and_adds_missing_scores():
    session = MagicMock()
    session.exec.return_value = result(all_values=())
    assert judging.sync_application_scores(session) == []

    first_id, second_id = uuid.uuid4(), uuid.uuid4()
    existing = score(first_id)
    inserted = score(second_id)
    session.reset_mock()
    session.exec.side_effect = [
        result(all_values=(first_id, second_id)),
        result(),
        result(all_values=(existing, inserted)),
    ]

    scores = judging.sync_application_scores(session)

    assert [item.application_id for item in scores] == [first_id, second_id]
    assert session.exec.call_count == 3


def test_get_or_create_state_seen_and_busy_ids():
    judge_id = uuid.uuid4()
    session = MagicMock()
    state = JudgingJudgeState(judge_id=judge_id)
    session.exec.side_effect = [result(), result(first=state)]
    state = judging.get_or_create_judge_state(session, judge_id, lock=True)
    assert state.judge_id == judge_id

    winner_id, loser_id, busy_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    decision = JudgingDecision(
        request_id=uuid.uuid4(),
        judge_id=judge_id,
        winner_application_id=winner_id,
        loser_application_id=loser_id,
    )
    other_state = JudgingJudgeState(judge_id=uuid.uuid4(), left_application_id=busy_id)
    session.exec.side_effect = [
        result(all_values=(decision,)),
        result(all_values=(other_state,)),
    ]
    assert judging._seen_ids(session, judge_id) == {winner_id, loser_id}
    assert judging._busy_ids(session, judge_id) == {busy_id}


def test_assign_pair_reuses_an_active_pair():
    judge_id = uuid.uuid4()
    left, right = score(), score()
    state = JudgingJudgeState(
        judge_id=judge_id,
        left_application_id=left.application_id,
        right_application_id=right.application_id,
    )
    session = MagicMock()
    with (
        patch.object(judging, "sync_application_scores", return_value=[left, right]),
        patch.object(judging, "get_or_create_judge_state", return_value=state),
    ):
        assert judging.assign_pair(session, judge_id) == (left, right)
    session.commit.assert_called_once()


def test_assign_pair_returns_none_without_anchor_or_candidate():
    judge_id = uuid.uuid4()
    session = MagicMock()
    state = JudgingJudgeState(judge_id=judge_id)
    with (
        patch.object(judging, "sync_application_scores", return_value=[]),
        patch.object(judging, "get_or_create_judge_state", return_value=state),
        patch.object(judging, "_busy_ids", return_value=set()),
        patch.object(judging, "_seen_ids", return_value=set()),
    ):
        assert judging.assign_pair(session, judge_id) is None

    only = score()
    with (
        patch.object(judging, "sync_application_scores", return_value=[only]),
        patch.object(judging, "get_or_create_judge_state", return_value=state),
        patch.object(judging, "_busy_ids", return_value=set()),
        patch.object(judging, "_seen_ids", return_value=set()),
        patch.object(judging.random, "choice", return_value=only),
    ):
        assert judging.assign_pair(session, judge_id) is None


@pytest.mark.parametrize("explore", [True, False])
def test_assign_pair_selects_and_persists_pair(explore):
    judge_id = uuid.uuid4()
    left, right, busy = score(comparisons=0), score(comparisons=1), score()
    state = JudgingJudgeState(judge_id=judge_id)
    session = MagicMock()
    with (
        patch.object(
            judging, "sync_application_scores", return_value=[left, right, busy]
        ),
        patch.object(judging, "get_or_create_judge_state", return_value=state),
        patch.object(judging, "_busy_ids", return_value={busy.application_id}),
        patch.object(judging, "_seen_ids", return_value=set()),
        patch.object(judging.random, "choice", return_value=left),
        patch.object(judging.random, "random", return_value=0 if explore else 1),
        patch.object(judging.random, "shuffle"),
        patch.object(judging.crowd_bt, "expected_information_gain", return_value=1),
    ):
        assert judging.assign_pair(session, judge_id) == (left, right)
    assert state.left_application_id == left.application_id
    assert state.right_application_id == right.application_id
    session.commit.assert_called_once()
    assert session.refresh.call_count == 2


def test_record_vote_reuses_duplicate_and_validates_it():
    judge_id = uuid.uuid4()
    winner, loser = score(), score()
    state = JudgingJudgeState(judge_id=judge_id)
    duplicate = JudgingDecision(
        request_id=uuid.uuid4(),
        judge_id=judge_id,
        winner_application_id=winner.application_id,
        loser_application_id=loser.application_id,
    )
    session = MagicMock()
    session.exec.return_value = result(first=duplicate)
    session.get.side_effect = [winner, loser]
    with patch.object(judging, "get_or_create_judge_state", return_value=state):
        returned = judging.record_vote(
            session,
            judge_id,
            duplicate.request_id,
            winner.application_id,
            loser.application_id,
            winner.application_id,
        )
    assert returned[:3] == (duplicate, winner, loser)

    duplicate.judge_id = uuid.uuid4()
    with (
        patch.object(judging, "get_or_create_judge_state", return_value=state),
        pytest.raises(ValueError, match="another judge"),
    ):
        judging.record_vote(
            session,
            judge_id,
            duplicate.request_id,
            uuid.uuid4(),
            uuid.uuid4(),
            uuid.uuid4(),
        )

    duplicate.judge_id = judge_id
    session.get.side_effect = [None, loser]
    with (
        patch.object(judging, "get_or_create_judge_state", return_value=state),
        pytest.raises(RuntimeError, match="missing score"),
    ):
        judging.record_vote(
            session,
            judge_id,
            duplicate.request_id,
            uuid.uuid4(),
            uuid.uuid4(),
            uuid.uuid4(),
        )


def test_record_vote_validation_errors():
    judge_id = uuid.uuid4()
    left_id, right_id = uuid.uuid4(), uuid.uuid4()
    state = JudgingJudgeState(
        judge_id=judge_id,
        left_application_id=left_id,
        right_application_id=right_id,
    )
    session = MagicMock()
    session.exec.return_value = result(first=None)
    with patch.object(judging, "get_or_create_judge_state", return_value=state):
        with pytest.raises(ValueError, match="active assignment"):
            judging.record_vote(
                session, judge_id, uuid.uuid4(), right_id, left_id, left_id
            )
        with pytest.raises(ValueError, match="Winner"):
            judging.record_vote(
                session, judge_id, uuid.uuid4(), left_id, right_id, uuid.uuid4()
            )

        session.exec.side_effect = [result(first=None), result(all_values=())]
        with pytest.raises(ValueError, match="not eligible"):
            judging.record_vote(
                session, judge_id, uuid.uuid4(), left_id, right_id, left_id
            )


def test_record_vote_updates_scores_and_state():
    judge_id = uuid.uuid4()
    left, right = score(), score()
    state = JudgingJudgeState(
        judge_id=judge_id,
        left_application_id=left.application_id,
        right_application_id=right.application_id,
    )
    session = MagicMock()
    session.exec.side_effect = [result(first=None), result(all_values=(left, right))]
    update = SimpleNamespace(
        alpha=11.0,
        beta=2.0,
        winner_mu=0.5,
        winner_sigma_sq=0.8,
        loser_mu=-0.5,
        loser_sigma_sq=0.8,
    )
    with (
        patch.object(judging, "get_or_create_judge_state", return_value=state),
        patch.object(judging.crowd_bt, "update", return_value=update),
    ):
        decision, winner, loser, reliability = judging.record_vote(
            session,
            judge_id,
            uuid.uuid4(),
            left.application_id,
            right.application_id,
            left.application_id,
        )
    assert (winner, loser) == (left, right)
    assert decision.winner_application_id == left.application_id
    assert left.comparison_count == right.comparison_count == 1
    assert state.left_application_id == right.application_id
    assert state.right_application_id is None
    assert reliability == pytest.approx(11 / 13)
    session.commit.assert_called_once()


def test_record_vote_recovers_concurrent_idempotent_commit():
    judge_id = uuid.uuid4()
    request_id = uuid.uuid4()
    left, right = score(), score()
    state = JudgingJudgeState(
        judge_id=judge_id,
        left_application_id=left.application_id,
        right_application_id=right.application_id,
    )
    duplicate = JudgingDecision(
        request_id=request_id,
        judge_id=judge_id,
        winner_application_id=left.application_id,
        loser_application_id=right.application_id,
    )
    session = MagicMock()
    session.exec.side_effect = [
        result(first=None),
        result(all_values=(left, right)),
        result(first=duplicate),
    ]
    session.commit.side_effect = IntegrityError("insert", {}, Exception("duplicate"))
    session.get.side_effect = [left, right, state]
    update = SimpleNamespace(
        alpha=11.0,
        beta=2.0,
        winner_mu=0.5,
        winner_sigma_sq=0.8,
        loser_mu=-0.5,
        loser_sigma_sq=0.8,
    )

    with (
        patch.object(judging, "get_or_create_judge_state", return_value=state),
        patch.object(judging.crowd_bt, "update", return_value=update),
    ):
        returned = judging.record_vote(
            session,
            judge_id,
            request_id,
            left.application_id,
            right.application_id,
            left.application_id,
        )

    assert returned[:3] == (duplicate, left, right)
    assert returned[3] == pytest.approx(11 / 13)
    session.rollback.assert_called_once()


def test_record_vote_rejects_concurrent_request_id_owned_by_another_judge():
    judge_id = uuid.uuid4()
    request_id = uuid.uuid4()
    left, right = score(), score()
    state = JudgingJudgeState(
        judge_id=judge_id,
        left_application_id=left.application_id,
        right_application_id=right.application_id,
    )
    duplicate = JudgingDecision(
        request_id=request_id,
        judge_id=uuid.uuid4(),
        winner_application_id=left.application_id,
        loser_application_id=right.application_id,
    )
    session = MagicMock()
    session.exec.side_effect = [
        result(first=None),
        result(all_values=(left, right)),
        result(first=duplicate),
    ]
    session.commit.side_effect = IntegrityError("insert", {}, Exception("duplicate"))

    with (
        patch.object(judging, "get_or_create_judge_state", return_value=state),
        patch.object(
            judging.crowd_bt,
            "update",
            return_value=SimpleNamespace(
                alpha=11.0,
                beta=2.0,
                winner_mu=0.5,
                winner_sigma_sq=0.8,
                loser_mu=-0.5,
                loser_sigma_sq=0.8,
            ),
        ),
        pytest.raises(ValueError, match="another judge"),
    ):
        judging.record_vote(
            session,
            judge_id,
            request_id,
            left.application_id,
            right.application_id,
            left.application_id,
        )


def test_admin_judging_endpoints():
    user = SimpleNamespace(uid=uuid.uuid4())
    session = MagicMock()
    left, right = score(mu=2), score(mu=1)

    with patch.object(judging_router, "assign_pair", return_value=None):
        with pytest.raises(HTTPException) as exc:
            judging_router.get_pair(session, user)
        assert exc.value.status_code == 404
    with patch.object(judging_router, "assign_pair", return_value=(left, right)):
        response = judging_router.get_pair(session, user)
        assert response.left.application_id == left.application_id

    vote = JudgingVoteRequest(
        request_id=uuid.uuid4(),
        left_application_id=left.application_id,
        right_application_id=right.application_id,
        winner_application_id=left.application_id,
    )
    with patch.object(
        judging_router, "record_vote", side_effect=ValueError("bad vote")
    ):
        with pytest.raises(HTTPException) as exc:
            judging_router.submit_decision(vote, session, user)
        assert exc.value.status_code == 409
        session.rollback.assert_called_once()

    decision = JudgingDecision(
        request_id=vote.request_id,
        judge_id=user.uid,
        winner_application_id=left.application_id,
        loser_application_id=right.application_id,
    )
    with patch.object(
        judging_router, "record_vote", return_value=(decision, left, right, 0.9)
    ):
        response = judging_router.submit_decision(vote, session, user)
        assert response.judge_reliability == 0.9


def test_rankings_handles_empty_and_ranked_scores():
    session = MagicMock()
    session.exec.return_value = result(all_values=())
    assert judging_router.get_rankings(session) == []

    first, second = score(mu=2), score(mu=1)
    session.exec.return_value = result(
        all_values=(
            (first.application_id, first.mu, first.sigma_sq, first.comparison_count),
            (
                second.application_id,
                second.mu,
                second.sigma_sq,
                second.comparison_count,
            ),
        )
    )
    rankings = judging_router.get_rankings(session, offset=3, limit=2)
    assert [entry.rank for entry in rankings] == [4, 5]
