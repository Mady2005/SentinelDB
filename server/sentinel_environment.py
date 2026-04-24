from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass
from random import Random
from typing import Any

from pydantic import BaseModel, ConfigDict

from sentineldb_env.models import (
    OversightAction,
    OversightObservation,
    OversightTrace,
    SentinelAction,
    SentinelObservation,
    SentinelReward,
)

try:
    from openenv import Environment  # type: ignore
except ImportError:  # pragma: no cover
    class Environment:  # type: ignore
        """Fallback base class for local development without OpenEnv."""


ATTACK_TYPES = ("SQL_INJECTION", "DATA_EXFIL", "DESTRUCTIVE")
PROFILE_NAMES = ("noob", "stealth", "aggressive")


@dataclass
class QueryRecord:
    type: str
    raw: str
    source_id: str


class StepResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    obs: SentinelObservation | None
    reward: SentinelReward
    done: bool
    info: dict[str, Any]


class SentinelEnvironment(Environment):
    def __init__(self, max_steps: int = 100, seed: int = 7, oversight_budget: int = 5):
        self.max_steps = max_steps
        self.seed = seed
        self.oversight_budget = oversight_budget
        self.rng = Random(seed)
        self.state: dict[str, Any] = {}
        self.current_query: QueryRecord | None = None
        self.current_observation: SentinelObservation | None = None
        self.source_history: Counter[str] = Counter()
        self.source_attacks: Counter[str] = Counter()
        self.recent_events: deque[dict[str, int]] = deque(maxlen=12)
        self.profile_runtime: dict[str, Any] = {}
        self.reset()

    def _initial_state(self) -> dict[str, Any]:
        attacker_profile = self.rng.choice(PROFILE_NAMES)
        return {
            "real_db_health": 1.0,
            "real_db_compromised": False,
            "decoy_engagement": 0.0,
            "backup_available": True,
            "served_legit": 0,
            "successful_attacks": 0,
            "false_positives": 0,
            "backups_used": 0,
            "blocked_attacks": 0,
            "step": 0,
            "max_steps": self.max_steps,
            "attacker_profile": attacker_profile,
            "oversight_budget_total": self.oversight_budget,
            "oversight_used": 0,
            "correct_overrides": 0,
            "wrong_overrides": 0,
            "prevented_attacks": 0,
        }

    def reset(self) -> SentinelObservation:
        self.state = self._initial_state()
        self.source_history = Counter()
        self.source_attacks = Counter()
        self.recent_events = deque(maxlen=12)
        self.profile_runtime = {
            "aggressive_burst_left": 0,
            "aggressive_cooldown_left": 0,
        }
        self.current_query = self.sample_query(self.state["attacker_profile"])
        self.current_observation = self.build_observation(self.current_query, record_source=True)
        return self.current_observation

    def sample_query(self, profile: str) -> QueryRecord:
        source_id = f"src-{self.rng.randint(1, 8):02d}"
        attack_probability = self._attack_probability(profile)
        is_attack = self.rng.random() < attack_probability

        if not is_attack:
            raw = self.rng.choice(
                [
                    "SELECT id, balance FROM accounts WHERE customer_id = 1042",
                    "UPDATE sessions SET last_seen = NOW() WHERE session_id = 'a81'",
                    "SELECT item_id, quantity FROM inventory WHERE warehouse = 'blr-1'",
                    "INSERT INTO audit_log(event_type, actor) VALUES ('login', 'ops-bot')",
                    "SELECT * FROM orders WHERE created_at > NOW() - INTERVAL '1 day'",
                ]
            )
            return QueryRecord(type="benign", raw=raw, source_id=source_id)

        attack_type = self._sample_attack_type(profile)
        payloads = {
            "SQL_INJECTION": [
                "SELECT * FROM users WHERE email = 'a' OR 1=1 --'",
                "SELECT * FROM payments WHERE id = 4 UNION SELECT card_no, cvv FROM cards",
                "admin' OR 1=1 /* bypass */",
            ],
            "DATA_EXFIL": [
                "SELECT name, ssn FROM customers UNION SELECT api_key, secret FROM secrets",
                "EXPORT TABLE payroll TO 'attacker-bucket'",
                "COPY (SELECT * FROM pii) TO STDOUT",
            ],
            "DESTRUCTIVE": [
                "DROP TABLE transactions",
                "DELETE FROM backups WHERE created_at < NOW() - INTERVAL '30 day'",
                "TRUNCATE TABLE audit_log",
            ],
        }
        return QueryRecord(type=attack_type, raw=self.rng.choice(payloads[attack_type]), source_id=source_id)

    def _attack_probability(self, profile: str) -> float:
        if profile == "noob":
            return 0.65
        if profile == "stealth":
            return 0.16
        if self.profile_runtime["aggressive_burst_left"] > 0:
            self.profile_runtime["aggressive_burst_left"] -= 1
            return 0.9
        if self.profile_runtime["aggressive_cooldown_left"] > 0:
            self.profile_runtime["aggressive_cooldown_left"] -= 1
            return 0.08
        self.profile_runtime["aggressive_burst_left"] = self.rng.randint(2, 5)
        self.profile_runtime["aggressive_cooldown_left"] = self.rng.randint(2, 4)
        return 0.85

    def _sample_attack_type(self, profile: str) -> str:
        if profile == "noob":
            weights = [0.5, 0.2, 0.3]
        elif profile == "stealth":
            weights = [0.35, 0.45, 0.2]
        else:
            weights = [0.4, 0.2, 0.4]
        return self.rng.choices(ATTACK_TYPES, weights=weights, k=1)[0]

    def _recent_event_counts(self) -> tuple[int, int, int]:
        recent_blocked = sum(item["blocked"] for item in self.recent_events)
        recent_successful = sum(item["successful"] for item in self.recent_events)
        recent_false_positives = sum(item["false_positive"] for item in self.recent_events)
        return recent_blocked, recent_successful, recent_false_positives

    def build_observation(self, query: QueryRecord, record_source: bool) -> SentinelObservation:
        prior_queries = self.source_history[query.source_id]
        prior_attacks = self.source_attacks[query.source_id]
        if record_source:
            self.source_history[query.source_id] += 1
            if query.type != "benign":
                self.source_attacks[query.source_id] += 1

        recent_blocked, recent_successful, recent_false_positives = self._recent_event_counts()
        signals = self.extract_signals(query.raw)
        return SentinelObservation(
            query_raw=query.raw,
            query_length=len(query.raw),
            has_or_1_eq_1=signals["OR_1_EQ_1"],
            has_union_select=signals["UNION_SELECT_OR_EXPORT"],
            has_drop=signals["DESTRUCTIVE_DDL"],
            source_id=query.source_id,
            past_queries_from_source=prior_queries,
            past_attacks_from_source=prior_attacks,
            recent_attacks_blocked=recent_blocked,
            recent_attacks_successful=recent_successful,
            recent_false_positives=recent_false_positives,
            real_db_health=round(self.state["real_db_health"], 3),
            decoy_mode="active" if self.state["decoy_engagement"] > 0 else "inactive",
        )

    def attack_damage(self, attack_type: str) -> float:
        return {
            "SQL_INJECTION": 0.3,
            "DATA_EXFIL": 0.5,
            "DESTRUCTIVE": 0.7,
        }.get(attack_type, 0.4)

    def _remaining_oversight_budget(self) -> int:
        return max(self.state["oversight_budget_total"] - self.state["oversight_used"], 0)

    def _ensure_step_ready(self) -> tuple[QueryRecord, SentinelObservation]:
        if self.current_query is None or self.current_observation is None:
            raise RuntimeError("Environment has not been reset")
        if self.state["real_db_compromised"] or self.state["step"] >= self.state["max_steps"]:
            raise RuntimeError("Episode already completed")
        return self.current_query, self.current_observation

    def _prepare_next_observation(self, done: bool) -> SentinelObservation | None:
        if done:
            self.current_query = None
            self.current_observation = None
            return None
        self.current_query = self.sample_query(self.state["attacker_profile"])
        self.current_observation = self.build_observation(self.current_query, record_source=True)
        return self.current_observation

    def _base_info(self, query: QueryRecord) -> dict[str, Any]:
        return {
            "query_type": query.type,
            "source_id": query.source_id,
            "attacker_profile": self.state["attacker_profile"],
            "real_db_health": round(self.state["real_db_health"], 3),
            "served_legit": self.state["served_legit"],
            "successful_attacks": self.state["successful_attacks"],
            "false_positives": self.state["false_positives"],
            "blocked_attacks": self.state["blocked_attacks"],
            "decoy_engagement": self.state["decoy_engagement"],
            "step": self.state["step"],
        }

    def _execute_final_action(
        self,
        query: QueryRecord,
        executed_action: SentinelAction,
        oversight_trace: OversightTrace | None = None,
    ) -> StepResult:
        is_attack = query.type != "benign"
        reward_value = 0.0
        breakdown: dict[str, float] = {
            "service": 0.0,
            "security": 0.0,
            "backup_cost": 0.0,
            "oversight": 0.0,
            "terminal": 0.0,
        }
        event = {"blocked": 0, "successful": 0, "false_positive": 0}

        if not is_attack:
            if executed_action.action_type in {"ALLOW_REAL", "BACKUP_ALLOW"}:
                self.state["served_legit"] += 1
                reward_value += 1.0
                breakdown["service"] += 1.0
                if executed_action.action_type == "BACKUP_ALLOW" and self.state["backup_available"]:
                    self.state["backup_available"] = False
                    self.state["backups_used"] += 1
                    reward_value -= 0.2
                    breakdown["backup_cost"] -= 0.2
            else:
                self.state["false_positives"] += 1
                reward_value -= 0.5
                breakdown["service"] -= 0.5
                event["false_positive"] = 1
        else:
            if executed_action.action_type in {"ALLOW_REAL", "BACKUP_ALLOW"}:
                self.state["successful_attacks"] += 1
                self.state["real_db_health"] = max(0.0, self.state["real_db_health"] - self.attack_damage(query.type))
                reward_value -= 5.0
                breakdown["security"] -= 5.0
                event["successful"] = 1
                if executed_action.action_type == "BACKUP_ALLOW" and self.state["backup_available"]:
                    self.state["backup_available"] = False
                    self.state["backups_used"] += 1
                    reward_value -= 0.2
                    breakdown["backup_cost"] -= 0.2
                if self.state["real_db_health"] <= 0:
                    self.state["real_db_compromised"] = True
            elif executed_action.action_type == "ROUTE_DECOY":
                self.state["decoy_engagement"] += 1.0
                reward_value += 0.6
                breakdown["security"] += 0.6
                event["blocked"] = 1
            else:
                self.state["blocked_attacks"] += 1
                reward_value += 0.5
                breakdown["security"] += 0.5
                event["blocked"] = 1

        if oversight_trace is not None and oversight_trace.override_used:
            self.state["oversight_used"] += 1
            reward_value -= 0.1
            breakdown["oversight"] -= 0.1
            if is_attack and oversight_trace.proposed_action in {"ALLOW_REAL", "BACKUP_ALLOW"}:
                self.state["correct_overrides"] += 1
                self.state["prevented_attacks"] += 1
                reward_value += 1.0
                breakdown["oversight"] += 1.0
            elif not is_attack:
                self.state["wrong_overrides"] += 1
                reward_value -= 0.4
                breakdown["oversight"] -= 0.4
            elif oversight_trace.proposed_action in {"BLOCK", "ROUTE_DECOY"}:
                reward_value -= 0.2
                breakdown["oversight"] -= 0.2

        self.recent_events.append(event)
        self.state["step"] += 1
        done = self.state["step"] >= self.state["max_steps"] or self.state["real_db_compromised"]

        if done:
            terminal_bonus = 0.1 * self.state["decoy_engagement"]
            reward_value += terminal_bonus
            breakdown["terminal"] += terminal_bonus
            if self.state["real_db_compromised"]:
                reward_value -= 10.0
                breakdown["terminal"] -= 10.0

        info = self._base_info(query)
        if oversight_trace is not None:
            info["oversight"] = oversight_trace.model_dump()
            info["oversight_budget_remaining"] = self._remaining_oversight_budget()
            info["correct_overrides"] = self.state["correct_overrides"]
            info["wrong_overrides"] = self.state["wrong_overrides"]
            info["prevented_attacks"] = self.state["prevented_attacks"]

        next_obs = self._prepare_next_observation(done)
        reward = SentinelReward(
            value=round(reward_value, 4),
            breakdown={key: round(value, 4) for key, value in breakdown.items()},
        )
        return StepResult(obs=next_obs, reward=reward, done=done, info=info)

    def step(self, action: SentinelAction) -> StepResult:
        query, _ = self._ensure_step_ready()
        return self._execute_final_action(query, executed_action=action)

    def get_state(self) -> dict[str, Any]:
        total_queries = (
            self.state["served_legit"]
            + self.state["successful_attacks"]
            + self.state["false_positives"]
            + self.state["blocked_attacks"]
        )
        attack_total = self.state["successful_attacks"] + self.state["blocked_attacks"]
        benign_total = self.state["served_legit"] + self.state["false_positives"]
        oversight_used = self.state["oversight_used"]
        return {
            **self.state,
            "attack_success_rate": round(self.state["successful_attacks"] / attack_total, 4) if attack_total else 0.0,
            "false_positive_rate": round(self.state["false_positives"] / benign_total, 4) if benign_total else 0.0,
            "queries_seen": total_queries,
            "oversight_budget_remaining": self._remaining_oversight_budget(),
            "oversight_precision": round(self.state["correct_overrides"] / oversight_used, 4) if oversight_used else 0.0,
            "resilience_score": max(
                0.0,
                round(
                    100
                    - (self.state["successful_attacks"] * 18)
                    - (self.state["false_positives"] * 6)
                    - ((1.0 - self.state["real_db_health"]) * 40),
                    2,
                ),
            ),
        }

    def extract_signals(self, query_raw: str) -> dict[str, bool]:
        normalized = query_raw.upper()
        return {
            "OR_1_EQ_1": "OR 1=1" in normalized,
            "UNION_SELECT_OR_EXPORT": any(token in normalized for token in ("UNION SELECT", "COPY (", "EXPORT TABLE")),
            "DESTRUCTIVE_DDL": any(token in normalized for token in ("DROP", "TRUNCATE", "DELETE FROM BACKUPS", "ALTER TABLE")),
            "STACKED_QUERY": ";" in normalized.strip().rstrip(";"),
            "COMMENT_BYPASS": any(token in normalized for token in ("--", "/*", "*/")),
            "SENSITIVE_TABLE_ACCESS": any(token in normalized for token in ("SSN", "SECRET", "PII", "PAYROLL", "CARD_NO", "CVV", "API_KEY")),
            "PRIVILEGE_ESCALATION": any(token in normalized for token in ("GRANT ", "ALTER ROLE", "CREATE USER", "ADMIN'")),
        }

    def infer_query_type(self, query_raw: str) -> str:
        signals = self.extract_signals(query_raw)
        if signals["DESTRUCTIVE_DDL"] or signals["PRIVILEGE_ESCALATION"]:
            return "DESTRUCTIVE"
        if signals["UNION_SELECT_OR_EXPORT"] or signals["SENSITIVE_TABLE_ACCESS"]:
            return "DATA_EXFIL"
        if signals["OR_1_EQ_1"] or signals["STACKED_QUERY"] or signals["COMMENT_BYPASS"]:
            return "SQL_INJECTION"
        return "benign"

    def observation_from_raw_query(self, query_raw: str, source_id: str = "demo-user", record_source: bool = False) -> SentinelObservation:
        record = QueryRecord(type=self.infer_query_type(query_raw), raw=query_raw, source_id=source_id)
        return self.build_observation(record, record_source=record_source)

    def risk_summary(self, obs: SentinelObservation) -> dict[str, Any]:
        signals = self.extract_signals(obs.query_raw)
        suspicious_signals = [name for name, active in signals.items() if active]
        score = 8
        score += 60 if obs.has_drop else 0
        score += 34 if obs.has_union_select else 0
        score += 22 if obs.has_or_1_eq_1 else 0
        score += 12 if signals["STACKED_QUERY"] else 0
        score += 10 if signals["COMMENT_BYPASS"] else 0
        score += 23 if signals["SENSITIVE_TABLE_ACCESS"] else 0
        score += 18 if signals["PRIVILEGE_ESCALATION"] else 0
        score += min(obs.past_attacks_from_source * 8, 16)
        score += min(obs.recent_attacks_successful * 4, 12)
        score += 8 if obs.real_db_health < 0.5 else 0
        risk_score = max(0, min(100, score))
        threat_level = "SAFE"
        if risk_score >= 65:
            threat_level = "CRITICAL"
        elif risk_score >= 25 or obs.past_attacks_from_source > 1:
            threat_level = "WATCHLIST"

        rationale: list[str] = []
        if suspicious_signals:
            rationale.append(f"Matched high-risk query signals: {', '.join(suspicious_signals)}.")
        if obs.past_attacks_from_source > 0:
            rationale.append(f"Source {obs.source_id} has {obs.past_attacks_from_source} prior attack-linked queries.")
        if obs.recent_attacks_successful > 0:
            rationale.append("Recent successful attacks increase pressure to avoid the real database.")
        if obs.real_db_health < 0.5:
            rationale.append("Real database health is already degraded, so containment is more valuable.")
        if not rationale:
            rationale.append("No high-risk lexical indicators were detected, so normal service is preferred.")

        recommended_action = heuristic_action_for_observation(obs).action_type
        return {
            "risk_score": risk_score,
            "threat_level": threat_level,
            "suspicious_signals": suspicious_signals,
            "rationale": rationale,
            "recommended_action": recommended_action,
        }

    def build_oversight_observation(self, obs: SentinelObservation, proposed_action: SentinelAction) -> OversightObservation:
        summary = self.risk_summary(obs)
        return OversightObservation(
            sentinel_observation=obs,
            proposed_action=proposed_action.action_type,
            risk_score=summary["risk_score"],
            threat_level=summary["threat_level"],
            suspicious_signals=summary["suspicious_signals"],
            remaining_budget=self._remaining_oversight_budget(),
            interventions_used=self.state["oversight_used"],
            recent_successful_attacks=obs.recent_attacks_successful,
            recent_false_positives=obs.recent_false_positives,
        )

    def heuristic_oversight_decision(self, oversight_obs: OversightObservation) -> tuple[OversightAction, str]:
        if oversight_obs.remaining_budget <= 0:
            return OversightAction(decision="APPROVE"), "Budget exhausted, so oversight must defer to Sentinel."

        proposed_action = oversight_obs.proposed_action
        sentinel_obs = oversight_obs.sentinel_observation

        if proposed_action in {"ALLOW_REAL", "BACKUP_ALLOW"} and oversight_obs.risk_score >= 70:
            if sentinel_obs.has_drop or sentinel_obs.has_union_select or sentinel_obs.real_db_health < 0.55:
                return (
                    OversightAction(decision="OVERRIDE_TO_DECOY"),
                    "Risk is critical and the proposed allow path would expose the real database, so oversight reroutes to the decoy.",
                )
            return (
                OversightAction(decision="OVERRIDE_TO_BLOCK"),
                "Risk is critical and the proposed allow path is too dangerous, so oversight blocks the query.",
            )

        if proposed_action == "BLOCK" and oversight_obs.risk_score >= 55 and (
            sentinel_obs.real_db_health < 0.55 or sentinel_obs.past_attacks_from_source > 0
        ):
            return (
                OversightAction(decision="OVERRIDE_TO_DECOY"),
                "Oversight spends budget to preserve threat intelligence and keep the attacker away from the real database.",
            )

        return OversightAction(decision="APPROVE"), "Sentinel's proposal is consistent with the current risk picture."

    def _executed_action_from_trace(self, trace: OversightTrace) -> SentinelAction:
        if trace.oversight_decision == "OVERRIDE_TO_BLOCK":
            return SentinelAction(action_type="BLOCK")
        if trace.oversight_decision == "OVERRIDE_TO_DECOY":
            return SentinelAction(action_type="ROUTE_DECOY")
        return SentinelAction(action_type=trace.proposed_action)

    def apply_oversight(
        self,
        obs: SentinelObservation,
        proposed_action: SentinelAction,
        oversight_action: OversightAction | None = None,
        reason_override: str | None = None,
    ) -> OversightTrace:
        oversight_obs = self.build_oversight_observation(obs, proposed_action)
        if oversight_action is None:
            oversight_action, reason = self.heuristic_oversight_decision(oversight_obs)
        else:
            reason = reason_override or "Manual oversight decision applied."

        if oversight_obs.remaining_budget <= 0 and oversight_action.decision != "APPROVE":
            return OversightTrace(
                proposed_action=proposed_action.action_type,
                oversight_decision="APPROVE",
                executed_action=proposed_action.action_type,
                override_used=False,
                oversight_reason="Budget exhausted, so the override request was downgraded to approval.",
            )

        executed_action = proposed_action.action_type
        if oversight_action.decision == "OVERRIDE_TO_BLOCK":
            executed_action = "BLOCK"
        elif oversight_action.decision == "OVERRIDE_TO_DECOY":
            executed_action = "ROUTE_DECOY"

        return OversightTrace(
            proposed_action=proposed_action.action_type,
            oversight_decision=oversight_action.decision,
            executed_action=executed_action,
            override_used=executed_action != proposed_action.action_type,
            oversight_reason=reason,
        )

    def step_with_oversight(
        self,
        proposed_action: SentinelAction,
        oversight_action: OversightAction | None = None,
        reason_override: str | None = None,
    ) -> StepResult:
        query, obs = self._ensure_step_ready()
        trace = self.apply_oversight(obs, proposed_action, oversight_action=oversight_action, reason_override=reason_override)
        executed_action = self._executed_action_from_trace(trace)
        return self._execute_final_action(query, executed_action=executed_action, oversight_trace=trace)

    def explain_action(
        self,
        obs: SentinelObservation,
        action: SentinelAction,
        oversight_trace: OversightTrace | None = None,
    ) -> dict[str, Any]:
        summary = self.risk_summary(obs)
        suspicious = bool(summary["suspicious_signals"])
        target_db = "decoy" if action.action_type == "ROUTE_DECOY" else "real"
        if action.action_type == "BLOCK":
            target_db = "blocked"

        backup_status = "triggered" if action.action_type == "BACKUP_ALLOW" else "skipped"
        explanation = {
            "threat_level": summary["threat_level"],
            "target_db": target_db,
            "backup_status": backup_status,
            "suspicious_signals": summary["suspicious_signals"],
            "risk_score": summary["risk_score"],
            "rationale": summary["rationale"],
            "recommended_action": summary["recommended_action"],
            "sentinel_proposal": action.action_type,
            "executed_action": action.action_type,
            "oversight_decision": "APPROVE",
            "override_used": False,
            "oversight_reason": "Oversight did not intervene.",
            "oversight_budget_remaining": self._remaining_oversight_budget(),
        }
        explanation["log_lines"] = [
            f"[Watcher] Observed query: {obs.query_raw}",
            f"[Analyzer] Threat: {summary['threat_level']} (risk={summary['risk_score']}/100)",
            f"[Sentinel] Proposed: {action.action_type}",
        ]

        if oversight_trace is not None:
            explanation["executed_action"] = oversight_trace.executed_action
            explanation["oversight_decision"] = oversight_trace.oversight_decision
            explanation["override_used"] = oversight_trace.override_used
            explanation["oversight_reason"] = oversight_trace.oversight_reason
            final_target_db = target_db
            if oversight_trace.executed_action == "ROUTE_DECOY":
                final_target_db = "decoy"
            elif oversight_trace.executed_action == "BLOCK":
                final_target_db = "blocked"
            else:
                final_target_db = "real"
            explanation["target_db"] = final_target_db
            explanation["log_lines"].append(f"[Oversight] Decision: {oversight_trace.oversight_decision}")
            explanation["log_lines"].append(f"[Oversight] Reason: {oversight_trace.oversight_reason}")
            explanation["log_lines"].append(f"[Defender] Final action: {oversight_trace.executed_action}")
        else:
            explanation["log_lines"].append(f"[Defender] Final action: {action.action_type}")

        explanation["log_lines"].append(f"[Deception] DB: {explanation['target_db']}")
        explanation["log_lines"].append(f"[Migration] Backup: {backup_status}")
        if suspicious:
            explanation["log_lines"].append(f"[Signals] {', '.join(summary['suspicious_signals'])}")
        return explanation

    def preview_guarded_decision(
        self,
        query_raw: str,
        source_id: str = "demo-user",
        proposed_action: SentinelAction | None = None,
    ) -> dict[str, Any]:
        obs = self.observation_from_raw_query(query_raw, source_id=source_id, record_source=False)
        sentinel_action = proposed_action or heuristic_action_for_observation(obs)
        trace = self.apply_oversight(obs, sentinel_action)
        final_action = self._executed_action_from_trace(trace)
        explanation = self.explain_action(obs, sentinel_action, oversight_trace=trace)
        return {
            "observation": obs.model_dump(),
            "sentinel_action": sentinel_action.action_type,
            "final_action": final_action.action_type,
            "oversight_trace": trace.model_dump(),
            "explanation": explanation,
        }

    def run_demo_session_step(
        self,
        query_raw: str,
        source_id: str = "demo-user",
        action_override: str | None = None,
        oversight_enabled: bool = True,
    ) -> dict[str, Any]:
        inferred_type = self.infer_query_type(query_raw)
        record = QueryRecord(type=inferred_type, raw=query_raw, source_id=source_id)
        self.current_query = record
        obs = self.build_observation(record, record_source=True)
        self.current_observation = obs
        sentinel_action = SentinelAction(action_type=action_override) if action_override else heuristic_action_for_observation(obs)

        if oversight_enabled:
            result = self.step_with_oversight(sentinel_action)
            trace_data = result.info.get("oversight", {})
            trace = OversightTrace.model_validate(trace_data)
            final_action = SentinelAction(action_type=trace.executed_action)
            explanation = self.explain_action(obs, sentinel_action, oversight_trace=trace)
        else:
            result = self.step(sentinel_action)
            trace = None
            final_action = sentinel_action
            explanation = self.explain_action(obs, sentinel_action)

        return {
            "action": final_action.action_type,
            "recommended_action": explanation["recommended_action"],
            "target_db": explanation["target_db"],
            "threat_level": explanation["threat_level"],
            "risk_score": explanation["risk_score"],
            "backup_status": explanation["backup_status"],
            "suspicious_signals": explanation["suspicious_signals"],
            "rationale": explanation["rationale"],
            "reward": result.reward.model_dump(),
            "done": result.done,
            "observation": obs.model_dump(),
            "state": self.get_state(),
            "info": result.info,
            "log_lines": explanation["log_lines"],
            "sentinel_proposal": sentinel_action.action_type,
            "oversight_decision": trace.oversight_decision if trace is not None else "APPROVE",
            "executed_action": final_action.action_type,
            "override_used": trace.override_used if trace is not None else False,
            "oversight_reason": explanation["oversight_reason"],
            "oversight_budget_remaining": self.get_state()["oversight_budget_remaining"],
        }


def heuristic_action_for_observation(obs: SentinelObservation) -> SentinelAction:
    normalized = obs.query_raw.upper()
    suspicious_score = 0
    suspicious_score += 3 if obs.has_or_1_eq_1 else 0
    suspicious_score += 3 if obs.has_union_select else 0
    suspicious_score += 4 if obs.has_drop else 0
    suspicious_score += 2 if "COPY (" in normalized or "EXPORT TABLE" in normalized else 0
    suspicious_score += 2 if "DELETE FROM BACKUPS" in normalized else 0
    suspicious_score += 1 if obs.past_attacks_from_source > 0 else 0
    suspicious = suspicious_score >= 3

    if obs.real_db_health < 0.45 and suspicious_score >= 2:
        return SentinelAction(action_type="ROUTE_DECOY")
    if suspicious_score >= 5:
        return SentinelAction(action_type="ROUTE_DECOY")
    if suspicious:
        return SentinelAction(action_type="BLOCK")
    if obs.past_attacks_from_source > 2 and obs.recent_attacks_successful > 0:
        return SentinelAction(action_type="ROUTE_DECOY")
    return SentinelAction(action_type="ALLOW_REAL")
