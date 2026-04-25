from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class DemoQueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query_raw: str = Field(..., min_length=1)
    source_id: str = Field(default="demo-user", min_length=1)
    oversight_enabled: bool = True


class DemoQueryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: str
    sentinel_proposal: str
    oversight_decision: str
    executed_action: str
    override_used: bool
    oversight_reason: str
    oversight_budget_remaining: int
    recommended_action: str
    target_db: str
    threat_level: str
    risk_score: int
    backup_status: str
    suspicious_signals: list[str]
    failure_modes: list[str]
    rationale: list[str]
    reward_breakdown: dict[str, float]
    observation: dict
    state: dict
    log_lines: list[str]


class DemoSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query_raw: str = Field(..., min_length=1)
    source_id: str = Field(default="demo-user", min_length=1)
    action_override: Literal["ALLOW_REAL", "BLOCK", "ROUTE_DECOY", "BACKUP_ALLOW"] | None = None
    oversight_enabled: bool = True


class DemoSessionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: str
    sentinel_proposal: str
    oversight_decision: str
    executed_action: str
    override_used: bool
    oversight_reason: str
    oversight_budget_remaining: int
    recommended_action: str
    target_db: str
    threat_level: str
    risk_score: int
    backup_status: str
    suspicious_signals: list[str]
    failure_modes: list[str]
    rationale: list[str]
    reward: dict
    reward_breakdown: dict[str, float]
    done: bool
    observation: dict
    state: dict
    info: dict
    log_lines: list[str]


class DemoResetResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str
    observation: dict
    state: dict
    oversight_budget_remaining: int
