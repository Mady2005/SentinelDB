from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


ACTION_TYPES = ("ALLOW_REAL", "BLOCK", "ROUTE_DECOY", "BACKUP_ALLOW")
OVERSIGHT_ACTION_TYPES = ("APPROVE", "OVERRIDE_TO_BLOCK", "OVERRIDE_TO_DECOY")


class BaseSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SentinelObservation(BaseSchema):
    query_raw: str
    query_length: int = Field(..., ge=0)
    has_or_1_eq_1: bool
    has_union_select: bool
    has_drop: bool
    source_id: str
    past_queries_from_source: int = Field(..., ge=0)
    past_attacks_from_source: int = Field(..., ge=0)
    recent_attacks_blocked: int = Field(..., ge=0)
    recent_attacks_successful: int = Field(..., ge=0)
    recent_false_positives: int = Field(..., ge=0)
    real_db_health: float = Field(..., ge=0.0, le=1.0)
    decoy_mode: Literal["inactive", "active"]
    max_attack_success_rate: float = Field(default=0.15, ge=0.0, le=1.0)
    max_false_positive_rate: float = Field(default=0.10, ge=0.0, le=1.0)


class SentinelAction(BaseSchema):
    action_type: Literal["ALLOW_REAL", "BLOCK", "ROUTE_DECOY", "BACKUP_ALLOW"]

    @field_validator("action_type")
    @classmethod
    def normalize_action(cls, value: str) -> str:
        normalized = value.strip().upper()
        if normalized not in ACTION_TYPES:
            raise ValueError(f"action_type must be one of {ACTION_TYPES}")
        return normalized


class SentinelReward(BaseSchema):
    value: float
    breakdown: dict[str, float]


class OversightObservation(BaseSchema):
    sentinel_observation: SentinelObservation
    proposed_action: Literal["ALLOW_REAL", "BLOCK", "ROUTE_DECOY", "BACKUP_ALLOW"]
    risk_score: int = Field(..., ge=0, le=100)
    threat_level: Literal["SAFE", "WATCHLIST", "CRITICAL"]
    suspicious_signals: list[str]
    remaining_budget: int = Field(..., ge=0)
    interventions_used: int = Field(..., ge=0)
    recent_successful_attacks: int = Field(..., ge=0)
    recent_false_positives: int = Field(..., ge=0)


class OversightAction(BaseSchema):
    decision: Literal["APPROVE", "OVERRIDE_TO_BLOCK", "OVERRIDE_TO_DECOY"]

    @field_validator("decision")
    @classmethod
    def normalize_decision(cls, value: str) -> str:
        normalized = value.strip().upper()
        if normalized not in OVERSIGHT_ACTION_TYPES:
            raise ValueError(f"decision must be one of {OVERSIGHT_ACTION_TYPES}")
        return normalized


class OversightTrace(BaseSchema):
    proposed_action: Literal["ALLOW_REAL", "BLOCK", "ROUTE_DECOY", "BACKUP_ALLOW"]
    oversight_decision: Literal["APPROVE", "OVERRIDE_TO_BLOCK", "OVERRIDE_TO_DECOY"]
    executed_action: Literal["ALLOW_REAL", "BLOCK", "ROUTE_DECOY", "BACKUP_ALLOW"]
    override_used: bool
    oversight_reason: str


class EnvStepResult(BaseSchema):
    observation: SentinelObservation | None
    reward: float
    done: bool
    info: dict


class StepPayload(BaseSchema):
    obs: SentinelObservation | None
    reward: SentinelReward
    done: bool
    info: dict


class GuardedStepPayload(BaseSchema):
    obs: SentinelObservation | None
    reward: SentinelReward
    done: bool
    info: dict
    oversight: OversightTrace
