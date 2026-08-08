import uuid

from pydantic import BaseModel, ConfigDict


class JudgingScorePublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    application_id: uuid.UUID
    mu: float
    sigma_sq: float
    comparison_count: int


class JudgingPairResponse(BaseModel):
    left: JudgingScorePublic
    right: JudgingScorePublic


class JudgingVoteRequest(BaseModel):
    request_id: uuid.UUID
    left_application_id: uuid.UUID
    right_application_id: uuid.UUID
    winner_application_id: uuid.UUID


class JudgingDecisionResponse(BaseModel):
    decision_id: uuid.UUID
    request_id: uuid.UUID
    winner_application_id: uuid.UUID
    loser_application_id: uuid.UUID
    winner_score: JudgingScorePublic
    loser_score: JudgingScorePublic
    judge_reliability: float


class JudgingRankingEntry(JudgingScorePublic):
    rank: int
