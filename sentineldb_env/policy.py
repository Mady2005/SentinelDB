from __future__ import annotations

import re

from .models import SentinelAction, SentinelObservation


ACTION_PATTERN = re.compile(r"(ALLOW_REAL|BLOCK|ROUTE_DECOY|BACKUP_ALLOW)")


def build_prompt_from_observation(obs: SentinelObservation) -> str:
    return (
        "You are Sentinel, an AI DB defender. Output exactly one token from: "
        "ALLOW_REAL, BLOCK, ROUTE_DECOY, BACKUP_ALLOW.\n"
        f"Query: {obs.query_raw}\n"
        f"Suspicious tokens: OR_1_EQ_1={obs.has_or_1_eq_1}, UNION_SELECT={obs.has_union_select}, DROP={obs.has_drop}.\n"
        f"Source: {obs.source_id}, past_queries={obs.past_queries_from_source}, past_attacks={obs.past_attacks_from_source}.\n"
        f"Recent: blocked={obs.recent_attacks_blocked}, successful={obs.recent_attacks_successful}, false_positives={obs.recent_false_positives}.\n"
        f"DB health={obs.real_db_health}, decoy_mode={obs.decoy_mode}, "
        f"max_attack_success_rate={obs.max_attack_success_rate}, max_false_positive_rate={obs.max_false_positive_rate}.\n"
        "Answer with just the action token."
    )


def parse_action(text: str) -> SentinelAction:
    match = ACTION_PATTERN.search(text.upper())
    action = match.group(1) if match else "BLOCK"
    return SentinelAction(action_type=action)
