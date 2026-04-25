from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any

try:
    from datasets import Dataset
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from trl import GRPOConfig, GRPOTrainer
    from trl.experimental.openenv import generate_rollout_completions
except UnicodeDecodeError as exc:  # pragma: no cover
    raise SystemExit(
        "TRL import failed under the default Windows text encoding. "
        "Run this script with UTF-8 mode enabled, for example: python -X utf8 train_trl.py"
    ) from exc
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "Install training dependencies first: pip install -r requirements.txt"
    ) from exc

from sentineldb_env.client import SentinelEnv
from sentineldb_env.policy import build_prompt_from_observation, parse_action


def get_model_device(model: Any) -> Any:
    return next(model.parameters()).device


def write_training_artifacts(output_dir: Path, eval_rows: list[dict[str, float]], log_history: list[dict[str, Any]]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    training_log_path = output_dir / "training_log.csv"
    log_fieldnames = sorted({key for row in log_history for key in row.keys()}) if log_history else ["step", "loss"]
    with training_log_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=log_fieldnames)
        writer.writeheader()
        for row in log_history:
            writer.writerow(row)

    try:
        import matplotlib.pyplot as plt
    except ImportError:
        return

    plot_dir = output_dir / "plots"
    plot_dir.mkdir(parents=True, exist_ok=True)

    reward_x = [row["episode"] for row in eval_rows]
    reward_y = [row["episode_return"] for row in eval_rows]
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(reward_x, reward_y, marker="o", linewidth=2, color="#22c55e")
    ax.set_title("SentinelDB Training Reward Curve")
    ax.set_xlabel("Evaluation Episode")
    ax.set_ylabel("Episode Return")
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(plot_dir / "reward_curve.png", dpi=180)
    plt.close(fig)

    loss_points = [row for row in log_history if "loss" in row]
    fig, ax = plt.subplots(figsize=(7, 4))
    if loss_points:
        ax.plot(
            [row.get("step", idx + 1) for idx, row in enumerate(loss_points)],
            [float(row["loss"]) for row in loss_points],
            marker="o",
            linewidth=2,
            color="#0ea5e9",
        )
        ax.set_ylabel("Training Loss")
    else:
        ax.text(0.5, 0.5, "Loss logs unavailable", ha="center", va="center", fontsize=12)
        ax.set_yticks([])
    ax.set_title("SentinelDB Training Loss Curve")
    ax.set_xlabel("Training Step")
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(plot_dir / "loss_curve.png", dpi=180)
    plt.close(fig)


def generate_completion_texts(trainer: GRPOTrainer, prompts: list[str]) -> tuple[list[dict[str, Any]], list[str]]:
    tokenizer = trainer.processing_class
    try:
        outputs = generate_rollout_completions(trainer, prompts)
        texts = [
            out.get("text") or tokenizer.decode(out["completion_ids"], skip_special_tokens=True)
            for out in outputs
        ]
        return outputs, texts
    except RuntimeError as exc:
        if "require vLLM" not in str(exc):
            raise
        outputs = []
        texts = []
        model_device = get_model_device(trainer.model)
        for prompt in prompts:
            encoded = tokenizer(prompt, return_tensors="pt").to(model_device)
            generated = trainer.model.generate(**encoded, max_new_tokens=8)
            completion_ids = generated[0][encoded["input_ids"].shape[1]:].tolist()
            text = tokenizer.decode(completion_ids, skip_special_tokens=True)
            outputs.append(
                {
                    "prompt_ids": encoded["input_ids"][0].tolist(),
                    "completion_ids": completion_ids,
                    "logprobs": [],
                    "text": text,
                }
            )
            texts.append(text)
        return outputs, texts


def run_episode(env: SentinelEnv, tokenizer: Any, model: Any, max_new_tokens: int = 4) -> tuple[float, dict[str, float]]:
    obs = env.reset()
    done = False
    episode_return = 0.0
    last_info: dict[str, Any] = {}
    model_device = get_model_device(model)

    while not done:
        prompt = build_prompt_from_observation(obs)
        encoded = tokenizer(prompt, return_tensors="pt").to(model_device)
        generated = model.generate(**encoded, max_new_tokens=max_new_tokens)
        completion = tokenizer.decode(generated[0][encoded["input_ids"].shape[1]:], skip_special_tokens=True)
        action = parse_action(completion)
        result = env.step(action)
        episode_return += result.reward
        last_info = result.info
        done = result.done
        if result.observation is None:
            break
        obs = result.observation

    metrics = {
        "episode_return": episode_return,
        "attack_success_rate": last_info["successful_attacks"] / max(last_info["successful_attacks"] + last_info["blocked_attacks"], 1),
        "false_positive_rate": last_info["false_positives"] / max(last_info["served_legit"] + last_info["false_positives"], 1),
    }
    return episode_return, metrics


def build_rollout_func(env_url: str):
    def rollout_func(prompts: list[str], trainer: GRPOTrainer) -> dict[str, Any]:
        env_rewards: list[float] = []
        attack_success_rates: list[float] = []
        false_positive_rates: list[float] = []
        tokenizer = trainer.processing_class
        outputs, completion_texts = generate_completion_texts(trainer, prompts)
        prompt_ids = [out["prompt_ids"] for out in outputs]
        completion_ids = [out["completion_ids"] for out in outputs]
        logprobs = [out["logprobs"] for out in outputs]

        with SentinelEnv(env_url).sync() as env:
            for out, completion_text in zip(outputs, completion_texts, strict=False):
                obs = env.reset()
                done = False
                episode_return = 0.0
                last_info: dict[str, Any] = {}
                turn_budget = 8

                while not done and turn_budget > 0:
                    action = parse_action(completion_text)
                    result = env.step(action)
                    episode_return += result.reward
                    last_info = result.info
                    done = result.done
                    if result.observation is None:
                        break
                    obs = result.observation
                    turn_budget -= 1
                    if not done and turn_budget > 0:
                        prompt_text = build_prompt_from_observation(obs)
                        next_out, next_texts = generate_completion_texts(trainer, [prompt_text])
                        completion_text = next_texts[0]
                        out = next_out

                attack_total = last_info.get("successful_attacks", 0) + last_info.get("blocked_attacks", 0)
                benign_total = last_info.get("served_legit", 0) + last_info.get("false_positives", 0)
                env_rewards.append(float(episode_return))
                attack_success_rates.append(last_info.get("successful_attacks", 0) / attack_total if attack_total else 0.0)
                false_positive_rates.append(last_info.get("false_positives", 0) / benign_total if benign_total else 0.0)

        return {
            "prompt_ids": prompt_ids,
            "completion_ids": completion_ids,
            "logprobs": logprobs,
            "env_reward": env_rewards,
            "attack_success_rate": attack_success_rates,
            "false_positive_rate": false_positive_rates,
        }

    return rollout_func


def reward_from_env(completions: list[str], **kwargs: Any) -> list[float]:
    env_rewards = kwargs.get("env_reward", [])
    if len(env_rewards) == len(completions):
        return [float(value) for value in env_rewards]
    return [0.0 for _ in completions]


def main() -> None:
    parser = argparse.ArgumentParser(description="Train a SentinelDB policy with TRL GRPO.")
    parser.add_argument("--env-url", default="http://localhost:8001/openenv")
    parser.add_argument("--model-name", default="Qwen/Qwen2.5-0.5B-Instruct")
    parser.add_argument("--output-dir", default="artifacts/grpo")
    parser.add_argument("--episodes", type=int, default=16)
    parser.add_argument("--use-cpu", action="store_true", help="Force training onto CPU instead of using GPU when available.")
    args = parser.parse_args()

    tokenizer = AutoTokenizer.from_pretrained(args.model_name)
    model = AutoModelForCausalLM.from_pretrained(args.model_name)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    dataset = Dataset.from_dict({"prompt": [f"episode-{idx}" for idx in range(args.episodes)]})

    training_args = GRPOConfig(
        output_dir=args.output_dir,
        per_device_train_batch_size=1,
        gradient_accumulation_steps=1,
        num_generations=2,
        generation_batch_size=2,
        learning_rate=1e-5,
        logging_steps=1,
        num_train_epochs=1,
        max_completion_length=8,
        use_vllm=False,
        use_cpu=args.use_cpu,
        gradient_checkpointing=False,
        save_strategy="no",
        report_to="none",
        do_train=True,
    )

    trainer = GRPOTrainer(
        model=model,
        args=training_args,
        train_dataset=dataset,
        reward_funcs=reward_from_env,
        processing_class=tokenizer,
        rollout_func=build_rollout_func(args.env_url),
    )

    train_result = trainer.train()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(output_dir / "model")
    tokenizer.save_pretrained(output_dir / "model")
    with SentinelEnv(args.env_url).sync() as env:
        eval_rows = []
        for episode_idx in range(1, min(6, args.episodes) + 1):
            episode_return, metrics = run_episode(env, tokenizer=tokenizer, model=model)
            eval_rows.append(
                {
                    "episode": episode_idx,
                    "episode_return": round(episode_return, 4),
                    "attack_success_rate": round(metrics["attack_success_rate"], 4),
                    "false_positive_rate": round(metrics["false_positive_rate"], 4),
                }
            )
    with (output_dir / "rollout_summary.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["episode", "episode_return", "attack_success_rate", "false_positive_rate"])
        writer.writeheader()
        writer.writerows(eval_rows)
    log_history = list(trainer.state.log_history)
    if train_result.metrics:
        summary_row = {"step": trainer.state.global_step, **train_result.metrics}
        if "train_loss" in train_result.metrics and "loss" not in summary_row:
            summary_row["loss"] = train_result.metrics["train_loss"]
        log_history.append(summary_row)
    write_training_artifacts(output_dir, eval_rows=eval_rows, log_history=log_history)


if __name__ == "__main__":
    main()
