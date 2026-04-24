from __future__ import annotations

from fastapi.testclient import TestClient

from sentineldb_env.models import SentinelAction
from server.app import app
from server.sentinel_environment import SentinelEnvironment, heuristic_action_for_observation


def run_policy(env: SentinelEnvironment, policy_name: str) -> tuple[float, dict]:
    obs = env.reset()
    done = False
    total_reward = 0.0
    last_info = {}

    while not done:
        if policy_name == "always_allow":
            action = SentinelAction(action_type="ALLOW_REAL")
        elif policy_name == "always_block":
            action = SentinelAction(action_type="BLOCK")
        else:
            action = heuristic_action_for_observation(obs)

        result = env.step(action)
        total_reward += result.reward.value
        last_info = result.info
        done = result.done
        if result.obs is None:
            break
        obs = result.obs

    return total_reward, last_info


def test_reset_returns_typed_observation() -> None:
    env = SentinelEnvironment(seed=11)
    obs = env.reset()

    assert obs.query_raw
    assert 0.0 <= obs.real_db_health <= 1.0
    assert obs.decoy_mode in {"inactive", "active"}


def test_always_allow_is_vulnerable() -> None:
    env = SentinelEnvironment(seed=3)
    total_reward, info = run_policy(env, "always_allow")

    assert info["successful_attacks"] >= 1
    assert info["real_db_health"] < 1.0
    assert total_reward < 0


def test_always_block_causes_false_positives() -> None:
    env = SentinelEnvironment(seed=13)
    total_reward, info = run_policy(env, "always_block")

    assert info["false_positives"] >= 1
    assert total_reward < 60


def test_heuristic_beats_always_allow_on_same_seed() -> None:
    allow_env = SentinelEnvironment(seed=23)
    heuristic_env = SentinelEnvironment(seed=23)

    allow_reward, _ = run_policy(allow_env, "always_allow")
    heuristic_reward, heuristic_info = run_policy(heuristic_env, "heuristic")

    assert heuristic_reward > allow_reward
    assert heuristic_info["successful_attacks"] <= allow_env.get_state()["successful_attacks"] or heuristic_info["real_db_health"] >= allow_env.get_state()["real_db_health"]


def test_demo_explanation_flags_obvious_attack() -> None:
    env = SentinelEnvironment(seed=5)
    obs = env.observation_from_raw_query("DROP TABLE transactions", source_id="demo-user")
    action = heuristic_action_for_observation(obs)
    explanation = env.explain_action(obs, action)

    assert action.action_type in {"BLOCK", "ROUTE_DECOY"}
    assert explanation["threat_level"] == "CRITICAL"
    assert "DESTRUCTIVE_DDL" in explanation["suspicious_signals"]


def test_risk_summary_includes_sensitive_exfiltration_signals() -> None:
    env = SentinelEnvironment(seed=7)
    obs = env.observation_from_raw_query(
        "SELECT name, ssn FROM customers UNION SELECT api_key, secret FROM secrets",
        source_id="partner-api-09",
    )
    summary = env.risk_summary(obs)

    assert summary["risk_score"] >= 65
    assert summary["threat_level"] == "CRITICAL"
    assert "UNION_SELECT_OR_EXPORT" in summary["suspicious_signals"]
    assert "SENSITIVE_TABLE_ACCESS" in summary["suspicious_signals"]


def test_session_step_updates_state_and_returns_reward() -> None:
    env = SentinelEnvironment(seed=17)
    env.reset()

    result = env.run_demo_session_step("DROP TABLE transactions", source_id="unknown-console")

    assert result["action"] in {"BLOCK", "ROUTE_DECOY"}
    assert result["reward"]["value"] >= 0.5
    assert result["state"]["queries_seen"] == 1


def test_demo_session_api_reset_and_step() -> None:
    client = TestClient(app)

    reset_response = client.post("/api/demo/session/reset")
    assert reset_response.status_code == 200
    assert "state" in reset_response.json()

    step_response = client.post(
        "/api/demo/session/step",
        json={
            "query_raw": "admin' OR 1=1 /* bypass */",
            "source_id": "unknown-console",
        },
    )
    body = step_response.json()
    assert step_response.status_code == 200
    assert body["risk_score"] >= 50
    assert body["action"] in {"BLOCK", "ROUTE_DECOY"}
    assert body["state"]["queries_seen"] >= 1
