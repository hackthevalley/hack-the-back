from dataclasses import dataclass
from math import exp, isfinite, lgamma, log

MU_PRIOR = 0.0
SIGMA_SQ_PRIOR = 1.0
ALPHA_PRIOR = 10.0
BETA_PRIOR = 1.0
GAMMA = 0.1
KAPPA = 0.0001
EPSILON = 0.25


@dataclass(frozen=True)
class UpdateResult:
    alpha: float
    beta: float
    winner_mu: float
    winner_sigma_sq: float
    loser_mu: float
    loser_sigma_sq: float


def _sigmoid(value: float) -> float:
    if value >= 0:
        z = exp(-value)
        return 1.0 / (1.0 + z)
    z = exp(value)
    return z / (1.0 + z)


def _digamma(value: float) -> float:
    result = 0.0
    while value < 8.0:
        result -= 1.0 / value
        value += 1.0
    inverse = 1.0 / value
    inverse_sq = inverse * inverse
    return result + log(value) - 0.5 * inverse - inverse_sq * (
        1.0 / 12.0
        - inverse_sq * (1.0 / 120.0 - inverse_sq * (1.0 / 252.0))
    )


def _annotator_update(
    alpha: float,
    beta: float,
    winner_mu: float,
    winner_sigma_sq: float,
    loser_mu: float,
    loser_sigma_sq: float,
) -> tuple[float, float, float]:
    p = _sigmoid(winner_mu - loser_mu)
    c1 = p + 0.5 * (winner_sigma_sq + loser_sigma_sq) * p * (1 - p) * (1 - 2 * p)
    c1 = min(max(c1, 1e-9), 1 - 1e-9)
    c2 = 1 - c1
    c = (c1 * alpha + c2 * beta) / (alpha + beta)
    expectation = (
        c1 * (alpha + 1) * alpha + c2 * alpha * beta
    ) / (c * (alpha + beta + 1) * (alpha + beta))
    expectation_sq = (
        c1 * (alpha + 2) * (alpha + 1) * alpha
        + c2 * (alpha + 1) * alpha * beta
    ) / (c * (alpha + beta + 2) * (alpha + beta + 1) * (alpha + beta))
    variance = max(expectation_sq - expectation * expectation, 1e-12)
    common = max(expectation - expectation_sq, 1e-12) / variance
    return max(common * expectation, KAPPA), max(common * (1 - expectation), KAPPA), c


def update(
    alpha: float,
    beta: float,
    winner_mu: float,
    winner_sigma_sq: float,
    loser_mu: float,
    loser_sigma_sq: float,
) -> UpdateResult:
    new_alpha, new_beta, _ = _annotator_update(
        alpha, beta, winner_mu, winner_sigma_sq, loser_mu, loser_sigma_sq
    )
    p = _sigmoid(winner_mu - loser_mu)
    reliable_winner_probability = alpha * p / (alpha * p + beta * (1 - p))
    multiplier = reliable_winner_probability - p
    curvature = reliable_winner_probability * (1 - reliable_winner_probability) - p * (1 - p)

    result = UpdateResult(
        alpha=new_alpha,
        beta=new_beta,
        winner_mu=winner_mu + winner_sigma_sq * multiplier,
        winner_sigma_sq=winner_sigma_sq * max(1 + winner_sigma_sq * curvature, KAPPA),
        loser_mu=loser_mu - loser_sigma_sq * multiplier,
        loser_sigma_sq=loser_sigma_sq * max(1 + loser_sigma_sq * curvature, KAPPA),
    )
    positive_values = (
        result.alpha,
        result.beta,
        result.winner_sigma_sq,
        result.loser_sigma_sq,
    )
    if not all(isfinite(value) and value > 0 for value in positive_values):
        raise ArithmeticError("Crowd-BT update produced invalid state")
    return result


def _gaussian_divergence(mu1: float, var1: float, mu2: float, var2: float) -> float:
    ratio = var1 / var2
    return (mu1 - mu2) ** 2 / (2 * var2) + (ratio - 1 - log(ratio)) / 2


def _beta_divergence(a1: float, b1: float, a2: float, b2: float) -> float:
    return (
        lgamma(a2) + lgamma(b2) - lgamma(a2 + b2)
        - lgamma(a1) - lgamma(b1) + lgamma(a1 + b1)
        + (a1 - a2) * _digamma(a1)
        + (b1 - b2) * _digamma(b1)
        + (a2 - a1 + b2 - b1) * _digamma(a1 + b1)
    )


def expected_information_gain(
    alpha: float,
    beta: float,
    mu_a: float,
    var_a: float,
    mu_b: float,
    var_b: float,
) -> float:
    outcome_a = update(alpha, beta, mu_a, var_a, mu_b, var_b)
    _, _, probability_a = _annotator_update(alpha, beta, mu_a, var_a, mu_b, var_b)
    outcome_b = update(alpha, beta, mu_b, var_b, mu_a, var_a)
    gain_a = (
        _gaussian_divergence(outcome_a.winner_mu, outcome_a.winner_sigma_sq, mu_a, var_a)
        + _gaussian_divergence(outcome_a.loser_mu, outcome_a.loser_sigma_sq, mu_b, var_b)
        + GAMMA * _beta_divergence(outcome_a.alpha, outcome_a.beta, alpha, beta)
    )
    gain_b = (
        _gaussian_divergence(outcome_b.loser_mu, outcome_b.loser_sigma_sq, mu_a, var_a)
        + _gaussian_divergence(outcome_b.winner_mu, outcome_b.winner_sigma_sq, mu_b, var_b)
        + GAMMA * _beta_divergence(outcome_b.alpha, outcome_b.beta, alpha, beta)
    )
    return probability_a * gain_a + (1 - probability_a) * gain_b
