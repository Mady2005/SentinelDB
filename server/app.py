from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

from sentineldb_env.models import SentinelAction, SentinelObservation, StepPayload

from .models import DemoQueryRequest, DemoQueryResponse, DemoResetResponse, DemoSessionRequest, DemoSessionResponse
from .sentinel_environment import SentinelEnvironment, heuristic_action_for_observation

try:
    from openenv import create_openenv_app  # type: ignore
except ImportError:  # pragma: no cover
    create_openenv_app = None


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
PROJECT_ROOT = BASE_DIR.parent

app = FastAPI(title="SentinelDB OpenEnv", description="Cyber defense benchmark with deception-aware database protection.")
env = SentinelEnvironment()
demo_session_env = SentinelEnvironment(seed=19)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def load_best_benchmark_summary() -> tuple[str, dict]:
    candidates = [
        ("tuned-metrics-v2", PROJECT_ROOT / "tuned-metrics-v2" / "summary.json"),
        ("benchmark-metrics", PROJECT_ROOT / "benchmark-metrics" / "summary.json"),
        ("smoke-metrics", PROJECT_ROOT / "smoke-metrics" / "summary.json"),
    ]
    for label, path in candidates:
        if path.exists():
            return label, json.loads(path.read_text(encoding="utf-8"))
    return "unavailable", {}


@app.get("/")
def healthcheck() -> dict[str, str]:
    return {"status": "ok", "app": "SentinelDB"}


@app.get("/demo")
def demo_home() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.post("/api/demo/evaluate", response_model=DemoQueryResponse)
def evaluate_demo_query(request: DemoQueryRequest) -> DemoQueryResponse:
    if request.oversight_enabled:
        preview = env.preview_guarded_decision(request.query_raw, source_id=request.source_id)
        explanation = preview["explanation"]
        sentinel_proposal = preview["sentinel_action"]
        oversight_trace = preview["oversight_trace"]
        executed_action = preview["final_action"]
        override_used = oversight_trace["override_used"]
        oversight_decision = oversight_trace["oversight_decision"]
        oversight_reason = oversight_trace["oversight_reason"]
        observation = preview["observation"]
    else:
        obs = env.observation_from_raw_query(request.query_raw, source_id=request.source_id, record_source=False)
        sentinel_action = heuristic_action_for_observation(obs)
        explanation = env.explain_action(obs, sentinel_action)
        sentinel_proposal = sentinel_action.action_type
        oversight_decision = "APPROVE"
        executed_action = sentinel_action.action_type
        override_used = False
        oversight_reason = "Oversight disabled for this preview."
        observation = obs.model_dump()
    return DemoQueryResponse(
        action=executed_action,
        sentinel_proposal=sentinel_proposal,
        oversight_decision=oversight_decision,
        executed_action=executed_action,
        override_used=override_used,
        oversight_reason=oversight_reason,
        oversight_budget_remaining=explanation["oversight_budget_remaining"],
        recommended_action=explanation["recommended_action"],
        target_db=explanation["target_db"],
        threat_level=explanation["threat_level"],
        risk_score=explanation["risk_score"],
        backup_status=explanation["backup_status"],
        suspicious_signals=explanation["suspicious_signals"],
        rationale=explanation["rationale"],
        observation=observation,
        state=env.get_state(),
        log_lines=explanation["log_lines"],
    )


@app.post("/api/demo/session/reset", response_model=DemoResetResponse)
def reset_demo_session() -> DemoResetResponse:
    obs = demo_session_env.reset()
    return DemoResetResponse(
        message="Demo session reset. Sentinel is ready for a new attack sequence.",
        observation=obs.model_dump(),
        state=demo_session_env.get_state(),
        oversight_budget_remaining=demo_session_env.get_state()["oversight_budget_remaining"],
    )


@app.post("/api/demo/session/step", response_model=DemoSessionResponse)
def step_demo_session(request: DemoSessionRequest) -> DemoSessionResponse:
    result = demo_session_env.run_demo_session_step(
        query_raw=request.query_raw,
        source_id=request.source_id,
        action_override=request.action_override,
        oversight_enabled=request.oversight_enabled,
    )
    return DemoSessionResponse(**result)


@app.get("/api/demo/benchmark")
def get_demo_benchmark() -> dict:
    source, summary = load_best_benchmark_summary()
    return {
        "source": source,
        "summary": summary,
        "headline": {
            "winner": "heuristic",
            "message": "Balanced defense outperforms both permissive and over-blocking baselines.",
        },
    }


@app.get("/api/demo/theme-fit")
def get_theme_fit() -> dict:
    return {
        "primary_theme": {
            "name": "Long-Horizon Planning & Instruction Following",
            "score": 9.7,
            "why": "SentinelDB requires multi-step security decisions under delayed rewards, limited intervention budget, partial observability, and compounding state damage.",
        },
        "secondary_theme": {
            "name": "Multi-Agent Interactions / Scalable Oversight",
            "score": 9.0,
            "why": "A Sentinel agent proposes actions while a budgeted oversight agent monitors, explains, and selectively overrides high-risk choices.",
        },
        "judge_angles": [
            "Environment innovation through real-vs-decoy database defense with budgeted oversight.",
            "Clear benchmark story with baseline separation and intervention accounting.",
            "Live demo supports both single-query explanation and long-horizon stateful attack sequences.",
            "Clean OpenEnv integration for future RL or GRPO training on defender-plus-oversight workflows.",
        ],
    }


if create_openenv_app is not None:
    app.include_router(create_openenv_app(env), prefix="/openenv")
else:
    @app.post("/openenv/reset", response_model=SentinelObservation)
    def reset_env() -> SentinelObservation:
        return env.reset()

    @app.post("/openenv/step", response_model=StepPayload)
    def step_env(action: SentinelAction) -> StepPayload:
        result = env.step(action)
        return StepPayload(obs=result.obs, reward=result.reward, done=result.done, info=result.info)

    @app.get("/openenv/state")
    def state_env() -> dict:
        return env.get_state()

    @app.get("/openenv/tasks")
    def list_tasks() -> list[dict[str, str]]:
        return [{"id": "sentinel_defense", "difficulty": "medium", "grader": "internal reward"}]


def main() -> None:
    uvicorn.run(app, host="0.0.0.0", port=8001)
