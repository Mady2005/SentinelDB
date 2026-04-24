from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any
from types import SimpleNamespace

import matplotlib.pyplot as plt
import pandas as pd
from transformers import AutoModelForCausalLM, AutoTokenizer

from sentineldb_env.client import SentinelEnv
from sentineldb_env.policy import build_prompt_from_observation, parse_action
from server.sentinel_environment import SentinelEnvironment


def choose_action(tokenizer, model, obs):
    prompt = build_prompt_from_observation(obs)
    encoded = tokenizer(prompt, return_tensors="pt")
    generated = model.generate(**encoded, max_new_tokens=8)
    completion = tokenizer.decode(generated[0][encoded["input_ids"].shape[1]:], skip_special_tokens=True)
    return parse_action(completion), completion


def step_env(env: Any, action):
    result = env.step(action)
    if hasattr(result, "observation"):
        return result
    return SimpleNamespace(
        observation=result.obs,
        reward=result.reward.value,
        done=result.done,
        info=result.info,
    )


def evaluate_model_policy(env: Any, tokenizer, model, n_episodes: int) -> list[dict[str, float | int | str]]:
    rows: list[dict[str, float | int | str]] = []
    for episode_idx in range(1, n_episodes + 1):
        obs = env.reset()
        done = False
        episode_return = 0.0
        last_info = {}
        sampled_completion = ""

        while not done:
            action, sampled_completion = choose_action(tokenizer, model, obs)
            result = step_env(env, action)
            episode_return += result.reward
            done = result.done
            last_info = result.info
            if result.observation is None:
                break
            obs = result.observation

        attack_total = last_info["successful_attacks"] + last_info["blocked_attacks"]
        benign_total = last_info["served_legit"] + last_info["false_positives"]
        rows.append(
            {
                "episode": episode_idx,
                "policy": "learned_model",
                "episode_return": round(episode_return, 4),
                "attack_success_rate": round(last_info["successful_attacks"] / attack_total, 4) if attack_total else 0.0,
                "false_positive_rate": round(last_info["false_positives"] / benign_total, 4) if benign_total else 0.0,
                "sample_completion": sampled_completion.strip(),
            }
        )
    return rows


def save_outputs(rows: list[dict[str, float | int | str]], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "model_metrics.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["episode", "policy", "episode_return", "attack_success_rate", "false_positive_rate", "sample_completion"])
        writer.writeheader()
        writer.writerows(rows)

    df = pd.DataFrame(rows)
    summary = (
        df[["episode_return", "attack_success_rate", "false_positive_rate"]]
        .mean()
        .round(4)
        .to_dict()
    )
    (output_dir / "model_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    plots_dir = output_dir / "plots"
    plots_dir.mkdir(parents=True, exist_ok=True)
    for metric in ("episode_return", "attack_success_rate", "false_positive_rate"):
        ax = df.plot(x="episode", y=metric, marker="o", figsize=(8, 4), title=f"Learned Model {metric.replace('_', ' ').title()}")
        ax.set_ylabel(metric.replace("_", " ").title())
        ax.set_xlabel("Episode")
        plt.tight_layout()
        plt.savefig(plots_dir / f"{metric}.png")
        plt.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate a trained SentinelDB language policy.")
    parser.add_argument("--env-url", default="local")
    parser.add_argument("--model-path", required=True)
    parser.add_argument("--episodes", type=int, default=10)
    parser.add_argument("--output-dir", default="model-eval")
    args = parser.parse_args()

    tokenizer = AutoTokenizer.from_pretrained(args.model_path)
    model = AutoModelForCausalLM.from_pretrained(args.model_path)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    if args.env_url == "local":
        env = SentinelEnvironment()
        rows = evaluate_model_policy(env, tokenizer=tokenizer, model=model, n_episodes=args.episodes)
    else:
        with SentinelEnv(args.env_url).sync() as env:
            rows = evaluate_model_policy(env, tokenizer=tokenizer, model=model, n_episodes=args.episodes)
    save_outputs(rows, Path(args.output_dir))


if __name__ == "__main__":
    main()
