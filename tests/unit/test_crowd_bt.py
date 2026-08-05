import math

import pytest

from app.services import crowd_bt


def test_priors_give_winner_positive_and_loser_negative_scores():
    result = crowd_bt.update(
        crowd_bt.ALPHA_PRIOR,
        crowd_bt.BETA_PRIOR,
        crowd_bt.MU_PRIOR,
        crowd_bt.SIGMA_SQ_PRIOR,
        crowd_bt.MU_PRIOR,
        crowd_bt.SIGMA_SQ_PRIOR,
    )

    assert result.winner_mu > 0
    assert result.loser_mu < 0
    assert result.winner_mu == pytest.approx(-result.loser_mu)
    assert result.alpha / (result.alpha + result.beta) > 0.5


def test_surprising_result_moves_scores_more_than_expected_result():
    expected = crowd_bt.update(10, 1, 2, 0.5, -2, 0.5)
    surprising = crowd_bt.update(10, 1, -2, 0.5, 2, 0.5)

    assert surprising.winner_mu - (-2) > expected.winner_mu - 2
    assert 2 - surprising.loser_mu > -2 - expected.loser_mu


def test_information_gain_is_finite_nonnegative_and_symmetric():
    forward = crowd_bt.expected_information_gain(10, 1, 0.4, 0.8, -0.2, 0.6)
    reverse = crowd_bt.expected_information_gain(10, 1, -0.2, 0.6, 0.4, 0.8)

    assert math.isfinite(forward)
    assert forward >= 0
    assert forward == pytest.approx(reverse)


def test_repeated_updates_remain_numerically_valid():
    alpha, beta = 10.0, 1.0
    winner_mu = loser_mu = 0.0
    winner_var = loser_var = 1.0
    for _ in range(500):
        result = crowd_bt.update(
            alpha, beta, winner_mu, winner_var, loser_mu, loser_var
        )
        alpha, beta = result.alpha, result.beta
        winner_mu, winner_var = result.winner_mu, result.winner_sigma_sq
        loser_mu, loser_var = result.loser_mu, result.loser_sigma_sq

    assert all(
        math.isfinite(value) and value > 0
        for value in (alpha, beta, winner_var, loser_var)
    )
