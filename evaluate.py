from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd

from sentineldb_env.client import SentinelEnv
from sentineldb_env.models import SentinelAction
from server.sentinel_environment import SentinelEnvironment, heuristic_action_for_observation


def evaluate_policy(env: Any, policy_name: str, n_episodes: int) -> list[dict[str, float | int | str]]:
    rows: list[dict[str, float | int | str]] = []
    for episode_idx in range(1, n_episodes + 1):
        obs = env.reset()
        done = False
        episode_return = 0.0
        last_info = {}

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
            if observation is None:
                break
            obs = observation

        attack_total = last_info["successful_attacks"] + last_info["blocked_attacks"]
        benign_total = last_info["served_legit"] + last_info["false_positives"]
        rows.append(
            {
                "episode": episode_idx,
                "policy": policy_name,
                "episode_return": round(episode_return, 4),
                "attack_success_rate": round(last_info["successful_attacks"] / attack_total, 4) if attack_total else 0.0,
                "false_positive_rate": round(last_info["false_positives"] / benign_total, 4) if benign_total else 0.0,
                "oversight_precision": round(last_info.get("correct_overrides", 0) / max(last_info.get("correct_overrides", 0) + last_info.get("wrong_overrides", 0), 1), 4),
            }
        )
    return rows


def save_metrics(rows: list[dict[str, float | int | str]], output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "metrics.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "episode",
                "policy",
                "episode_return",
                "attack_success_rate",
                "false_positive_rate",
                "oversight_precision",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)
    return csv_path


def save_summary(rows: list[dict[str, float | int | str]], output_dir: Path) -> Path:
    df = pd.DataFrame(rows)
    summary = (
        df.groupby("policy")[["episode_return", "attack_success_rate", "false_positive_rate", "oversight_precision"]]
        .mean()
        .round(4)
        .sort_values("episode_return", ascending=False)
        .to_dict(orient="index")
    )
    summary_path = output_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary_path


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
        for policy_name in policies:
            rows.extend(evaluate_policy(env, policy_name=policy_name, n_episodes=args.episodes))
    else:
        with SentinelEnv(args.env_url) as env:
            rows = []
            for policy_name in ("always_allow", "always_block", "heuristic"):
                rows.extend(evaluate_policy(env, policy_name=policy_name, n_episodes=args.episodes))

    csv_path = save_metrics(rows, output_dir)
    save_summary(rows, output_dir)
    plot_metrics(csv_path, output_dir / "plots")


if __name__ == "__main__":
    main()
