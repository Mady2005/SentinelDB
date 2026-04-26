from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd

from sentineldb_env.client import SentinelEnv
from sentineldb_env.models import SentinelAction
from server.sentinel_environment import SentinelEnvironment, heuristic_action_for_observation


def evaluate_policy(
    env: Any,
    policy_name: str,
    n_episodes: int,
) -> tuple[list[dict[str, float | int | str]], list[dict[str, float | int | str]]]:
    episode_rows: list[dict[str, float | int | str]] = []
    scenario_rows: list[dict[str, float | int | str]] = []
    for episode_idx in range(1, n_episodes + 1):
        obs = env.reset()
        done = False
        episode_return = 0.0
        last_info = {}
        scenario_counter: Counter[str] = Counter()
        prev_totals = {
            "successful_attacks": 0,
            "blocked_attacks": 0,
            "false_positives": 0,
            "served_legit": 0,
        }

        while not done:
            if policy_name == "always_allow":
                action = SentinelAction(action_type="ALLOW_REAL")
            elif policy_name == "always_block":
                action = SentinelAction(action_type="BLOCK")
            else:
                action = heuristic_action_for_observation(obs)

            if policy_name == "heuristic_guarded":
                if not hasattr(env, "step_with_oversight"):
                    raise ValueError("heuristic_guarded requires a local SentinelEnvironment with oversight support")
                result = env.step_with_oversight(action)
                observation = result.obs
                reward = result.reward.value
            else:
                result = env.step(action)
                observation = result.observation if hasattr(result, "observation") else result.obs
                reward = result.reward if hasattr(result, "reward") and isinstance(result.reward, float) else result.reward.value

            episode_return += reward
            done = result.done
            last_info = result.info
            scenario_label = str(last_info.get("scenario_label", "unknown"))
            scenario_counter[scenario_label] += 1
            delta_successful = int(last_info.get("successful_attacks", 0)) - prev_totals["successful_attacks"]
            delta_blocked = int(last_info.get("blocked_attacks", 0)) - prev_totals["blocked_attacks"]
            delta_false_positives = int(last_info.get("false_positives", 0)) - prev_totals["false_positives"]
            delta_served_legit = int(last_info.get("served_legit", 0)) - prev_totals["served_legit"]
            scenario_rows.append(
                {
                    "episode": episode_idx,
                    "policy": policy_name,
                    "attacker_profile": str(last_info.get("attacker_profile", "unknown")),
                    "scenario_label": scenario_label,
                    "query_type": str(last_info.get("query_type", "unknown")),
                    "step": int(last_info.get("step", 0)),
                    "step_reward": round(reward, 4),
                    "attack_successes": delta_successful,
                    "attacks_blocked": delta_blocked,
                    "false_positives": delta_false_positives,
                    "served_legit": delta_served_legit,
                }
            )
            prev_totals = {
                "successful_attacks": int(last_info.get("successful_attacks", 0)),
                "blocked_attacks": int(last_info.get("blocked_attacks", 0)),
                "false_positives": int(last_info.get("false_positives", 0)),
                "served_legit": int(last_info.get("served_legit", 0)),
            }
            if observation is None:
                break
            obs = observation

        attack_total = last_info["successful_attacks"] + last_info["blocked_attacks"]
        benign_total = last_info["served_legit"] + last_info["false_positives"]
        primary_scenario = "unknown"
        if scenario_counter:
            non_benign_scenarios = {label: count for label, count in scenario_counter.items() if not label.startswith("benign")}
            primary_scenario = (
                max(non_benign_scenarios, key=non_benign_scenarios.get)
                if non_benign_scenarios
                else max(scenario_counter, key=scenario_counter.get)
            )
        episode_rows.append(
            {
                "episode": episode_idx,
                "policy": policy_name,
                "attacker_profile": str(last_info.get("attacker_profile", "unknown")),
                "primary_scenario": primary_scenario,
                "episode_return": round(episode_return, 4),
                "attack_success_rate": round(last_info["successful_attacks"] / attack_total, 4) if attack_total else 0.0,
                "false_positive_rate": round(last_info["false_positives"] / benign_total, 4) if benign_total else 0.0,
                "oversight_precision": round(last_info.get("correct_overrides", 0) / max(last_info.get("correct_overrides", 0) + last_info.get("wrong_overrides", 0), 1), 4),
            }
        )
    return episode_rows, scenario_rows


def save_metrics(
    episode_rows: list[dict[str, float | int | str]],
    scenario_rows: list[dict[str, float | int | str]],
    output_dir: Path,
) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "metrics.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "episode",
                "policy",
                "attacker_profile",
                "primary_scenario",
                "episode_return",
                "attack_success_rate",
                "false_positive_rate",
                "oversight_precision",
            ],
        )
        writer.writeheader()
        writer.writerows(episode_rows)

    scenario_csv_path = output_dir / "scenario_metrics.csv"
    with scenario_csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "episode",
                "policy",
                "attacker_profile",
                "scenario_label",
                "query_type",
                "step",
                "step_reward",
                "attack_successes",
                "attacks_blocked",
                "false_positives",
                "served_legit",
            ],
        )
        writer.writeheader()
        writer.writerows(scenario_rows)
    return csv_path, scenario_csv_path


def save_summary(
    episode_rows: list[dict[str, float | int | str]],
    scenario_rows: list[dict[str, float | int | str]],
    output_dir: Path,
) -> tuple[Path, Path, Path]:
    df = pd.DataFrame(episode_rows)
    summary = (
        df.groupby("policy")[["episode_return", "attack_success_rate", "false_positive_rate", "oversight_precision"]]
        .mean()
        .round(4)
        .sort_values("episode_return", ascending=False)
        .to_dict(orient="index")
    )
    summary_path = output_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    profile_summary_df = (
        df.groupby(["policy", "attacker_profile"])[["episode_return", "attack_success_rate", "false_positive_rate", "oversight_precision"]]
        .mean()
        .round(4)
        .reset_index()
    )
    profile_summary_path = output_dir / "profile_summary.json"
    profile_summary_path.write_text(json.dumps(profile_summary_df.to_dict(orient="records"), indent=2), encoding="utf-8")

    scenario_df = pd.DataFrame(scenario_rows)
    scenario_summary_df = (
        scenario_df.groupby(["policy", "scenario_label"])
        .agg(
            steps=("scenario_label", "size"),
            avg_step_reward=("step_reward", "mean"),
            attack_successes=("attack_successes", "sum"),
            attacks_blocked=("attacks_blocked", "sum"),
            false_positives=("false_positives", "sum"),
            served_legit=("served_legit", "sum"),
        )
        .reset_index()
    )
    scenario_summary_df["attack_success_rate"] = scenario_summary_df.apply(
        lambda row: round(row["attack_successes"] / (row["attack_successes"] + row["attacks_blocked"]), 4)
        if (row["attack_successes"] + row["attacks_blocked"]) > 0
        else 0.0,
        axis=1,
    )
    scenario_summary_df["false_positive_rate"] = scenario_summary_df.apply(
        lambda row: round(row["false_positives"] / (row["false_positives"] + row["served_legit"]), 4)
        if (row["false_positives"] + row["served_legit"]) > 0
        else 0.0,
        axis=1,
    )
    scenario_summary_df["avg_step_reward"] = scenario_summary_df["avg_step_reward"].round(4)
    scenario_summary_path = output_dir / "scenario_summary.json"
    scenario_summary_path.write_text(
        json.dumps(
            scenario_summary_df[
                [
                    "policy",
                    "scenario_label",
                    "steps",
                    "avg_step_reward",
                    "attack_success_rate",
                    "false_positive_rate",
                ]
            ].to_dict(orient="records"),
            indent=2,
        ),
        encoding="utf-8",
    )
    return summary_path, profile_summary_path, scenario_summary_path


def plot_metrics(csv_path: Path, output_dir: Path) -> None:
    df = pd.read_csv(csv_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    for metric in ("attack_success_rate", "episode_return"):
        ax = df.groupby("policy")[metric].mean().plot(kind="bar", figsize=(7, 4), title=metric.replace("_", " ").title())
        ax.set_ylabel(metric.replace("_", " ").title())
        plt.tight_layout()
        plt.savefig(output_dir / f"{metric}.png")
        plt.close()
    for metric in ("attack_success_rate", "episode_return", "false_positive_rate", "oversight_precision"):
        ax = df.pivot(index="episode", columns="policy", values=metric).plot(
            figsize=(8, 4),
            marker="o",
            title=f"{metric.replace('_', ' ').title()} by Episode",
        )
        ax.set_ylabel(metric.replace("_", " ").title())
        ax.set_xlabel("Episode")
        plt.tight_layout()
        plt.savefig(output_dir / f"{metric}_lines.png")
        plt.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate scripted SentinelDB policies and plot metrics.")
    parser.add_argument("--env-url", default="local")
    parser.add_argument("--episodes", type=int, default=20)
    parser.add_argument("--output-dir", default="metrics")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    if args.env_url == "local":
        env: Any = SentinelEnvironment()
        policies = ("heuristic_guarded", "heuristic", "always_allow", "always_block")
        rows = []
        scenario_rows = []
        for policy_name in policies:
            policy_rows, policy_scenario_rows = evaluate_policy(env, policy_name=policy_name, n_episodes=args.episodes)
            rows.extend(policy_rows)
            scenario_rows.extend(policy_scenario_rows)
    else:
        with SentinelEnv(args.env_url) as env:
            rows = []
            scenario_rows = []
            for policy_name in ("always_allow", "always_block", "heuristic"):
                policy_rows, policy_scenario_rows = evaluate_policy(env, policy_name=policy_name, n_episodes=args.episodes)
                rows.extend(policy_rows)
                scenario_rows.extend(policy_scenario_rows)

    csv_path, _ = save_metrics(rows, scenario_rows, output_dir)
    save_summary(rows, scenario_rows, output_dir)
    plot_metrics(csv_path, output_dir / "plots")


if __name__ == "__main__":
    main()
