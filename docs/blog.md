---
title: "SentinelDB: Training Long-Horizon Cyber Defense Beyond Allow or Block"
thumbnail: /blog/assets/sentineldb/cover.png
authors:
  - user: sentineldb-team
tags:
  - reinforcement-learning
  - cybersecurity
  - openenv
  - trl
  - grpo
  - agentic-ai
---

# SentinelDB: Training Long-Horizon Cyber Defense Beyond Allow or Block

Most database defenses collapse into a binary choice: allow the query or block it. SentinelDB explores a harder and more realistic setting. A defender must keep real traffic flowing, catch malicious traffic, decide when to deceive attackers with a decoy database, and do all of that over long sessions where earlier mistakes affect later risk.

This is the core idea behind **SentinelDB**, our OpenEnv hackathon environment for training and evaluating long-horizon cyber-defense agents.

> **TL;DR** - SentinelDB is an OpenEnv benchmark where an agent defends a database against SQL injection, data exfiltration, privilege abuse, and destructive DDL attacks. The environment is stateful, partially observable, and shaped around the real security-availability tradeoff. Benchmark baselines show that both permissive and over-defensive policies fail, while balanced policies achieve high return with low attack success and low false positives.

---

## Why We Built It

Many benchmark environments are easy to verify but too shallow to teach useful behavior. Security is especially vulnerable to that failure mode. A toy benchmark can reward keyword blocking, string matching, or one-step classification, while completely missing what makes real defensive work hard:

- legitimate traffic must continue to flow
- suspicious traffic often looks partially benign
- operational issues matter alongside security issues
- defenders act under persistent state, not isolated one-step prompts

We wanted an environment that makes the correct policy **non-trivial**.

In SentinelDB:

- **always allow** fails because attacks succeed
- **always block** fails because availability collapses
- the winning policy must learn the security-availability tradeoff over time

That is the capability gap we target.

---

## What SentinelDB Models

SentinelDB is built on **OpenEnv 0.2.3** and simulates a live database under mixed benign and adversarial traffic. The environment keeps track of:

- current intercepted query
- source history and prior attack behavior
- recent attack outcomes
- real database health
- deception state
- false positives and operational pressure
- oversight intervention budget

This makes the environment explicitly **long-horizon**. Actions do not just affect the current step. They change the future risk profile of the session.

### Attacker Profiles

Each episode samples from one of several attacker styles:

| Profile | Behavior | Difficulty |
|---|---|---|
| **Noob** | Obvious SQLi and textbook attack strings | Easy |
| **Stealth** | Mostly benign-looking traffic with subtle exfiltration | Hard |
| **Aggressive** | Attack bursts followed by quiet phases | Medium |

These profiles matter because the same local action can be good or bad depending on the broader session context.

### The Action Space

The agent chooses one of four actions:

- `ALLOW_REAL`
- `BLOCK`
- `ROUTE_DECOY`
- `BACKUP_ALLOW`

`ROUTE_DECOY` is the distinctive action. Instead of rejecting suspicious traffic, the agent can silently redirect it to a decoy database. The attacker receives a plausible response, but the real database remains untouched.

This makes SentinelDB more than a filter. It becomes a strategic environment where deception is a first-class defensive option.

### Multi-Agent Oversight

SentinelDB also supports a two-role framing:

- **Sentinel** proposes the defensive action
- **Oversight** selectively intervenes under a limited budget

That gives the environment a strong secondary fit for **multi-agent interaction** while preserving its primary role as a long-horizon planning benchmark.

---

## What the Agent Sees

At each step, the agent observes a typed structured state rather than a loose text blob:

```python
class SentinelObservation(BaseModel):
    query_raw: str
    source_id: str

    has_union_select: bool
    has_or_one_equals_one: bool
    has_drop: bool
    has_truncate: bool
    has_copy_export: bool
    has_admin_bypass: bool
    has_grant_privilege: bool

    source_query_count: int
    source_attack_count: int
    recent_attack_successes: int

    real_db_health: float
    decoy_mode_active: bool
    false_positive_count: int
```

Recent versions of the environment also expose operational failure modes that make the task feel more realistic:

- schema mismatch pressure
- authorization or privilege risk
- timeout pressure
- rate-limit pressure

This is important. We did not want the benchmark to become "detect obvious SQL injection strings." We wanted a stateful decision problem where the model has to reason about **security, usability, and operational risk together**.

---

## Reward Design

Reward design is the heart of the environment.

If we rewarded only attack prevention, the agent could learn a degenerate shortcut: block everything. That gives low attack success but destroys usability. SentinelDB is explicitly designed to expose and penalize that failure mode.

### Reward Components

Each step combines multiple reward signals:

```text
+1.0   Service reward         - benign query correctly served
+0.5   Threat containment     - attack blocked or decoy-routed
+0.1x  Deception bonus        - additional reward for successful decoy engagement
-0.5   False positive         - benign traffic incorrectly blocked
-5.0   Attack allowed         - malicious traffic reaches the real database
-10.0  Terminal compromise    - severe failure with long-horizon consequence
```

The asymmetry is intentional:

- serving benign traffic well matters
- allowing attacks is much worse than a small mistake
- over-defensive behavior is visible through false-positive penalties
- long-horizon compromise dominates short-term local gains

This design makes the benchmark hard to game. A policy that maximizes blocking without solving the real task does not earn a strong overall score.

---

## Why This Is Not a Toy Environment

One of the easiest mistakes in RL environment design is to make an environment easy to verify but not faithful to the underlying task. We explicitly tried to avoid that.

SentinelDB is not just:

- a final-string verifier
- a regex success check
- a one-step classifier benchmark
- an LLM-as-judge setup

Instead, it includes:

- **persistent world state**
- **delayed consequences**
- **multi-signal deterministic reward**
- **deception as a strategic action**
- **operational failure modes**
- **false-positive penalties**
- **multi-agent oversight**

That is what gives it training value beyond a toy detection task.

---

## Benchmark Results

The benchmark already tells a strong story, even before talking about learned policies.

From our baseline evaluation:

| Policy | Episode Return | Attack Success Rate | False Positive Rate |
|---|---:|---:|---:|
| **Heuristic Sentinel** | **85.825** | **0.0** | **0.0** |
| Always Block | -4.0 | 0.0 | 1.0 |
| Always Allow | -19.975 | 1.0 | 0.0 |

This result is exactly what we wanted from the environment:

- **always allow** preserves availability but gets compromised
- **always block** preserves security but destroys usability
- **heuristic Sentinel** balances the tradeoff successfully

That means the benchmark is doing useful work. It is not rewarding a trivial extreme.

### Scenario Coverage

We also designed the environment to cover qualitatively different decision types:

- **Benign traffic**
  Example: `SELECT id, balance FROM accounts WHERE customer_id = 1042`

- **Operational anomaly**
  Example: `SELECT unknown_field FROM ghost_table`

- **Privilege escalation**
  Example: `GRANT ALL PRIVILEGES ON payroll TO analyst`

- **Exfiltration or destructive attack**
  Example: `SELECT name, ssn FROM customers UNION SELECT api_key, secret FROM secrets`

This scenario spread matters because it forces the benchmark to measure more than just attack keyword matching.

---

## The RL Training Pipeline

We built SentinelDB to be trainable end-to-end with TRL, not just hand-authored as a static benchmark.

### GRPO with TRL

We use TRL's `GRPOTrainer` to roll out episodes against the live OpenEnv environment and optimize policy behavior from environment reward:

```python
from trl import GRPOTrainer, GRPOConfig

trainer = GRPOTrainer(
    model=model,
    config=GRPOConfig(
        learning_rate=1e-5,
        max_completion_length=8,
    ),
    reward_funcs=[reward_from_env],
    train_dataset=episode_dataset,
)
trainer.train()
```

The action space is intentionally compact. The policy only needs to output one of the valid defense actions, which lets us focus learning pressure on the **decision quality**, not verbose text generation.

### Minimal Reproducible Training

For the hackathon submission, we provide:

- a public Colab notebook with the minimal reproducible training loop
- `train_trl.py` in the repository
- committed reward and loss plots
- a public Hugging Face Space hosting the environment

We also ran a completed compute-backed training job on Hugging Face during the onsite event as supporting evidence that the full remote training path works. That run used:

- `a10g-small` GPU hardware
- `Qwen/Qwen2.5-0.5B-Instruct`
- TRL / GRPO

The job completed successfully, logged non-zero environment reward during training (`reward_from_env/mean = 2.05`), recorded final training metrics (`train_loss = 0.005437`, `train_runtime = 25.38`), and wrote model shards successfully. We treat this as supporting evidence that the model is actually training against the SentinelDB OpenEnv environment rather than only being evaluated offline.

### What Training Teaches

The most important training lesson is not "the model learned to block attacks." A weak policy can do that by over-blocking everything.

The real target is:

- keep attack success low
- avoid false-positive collapse
- preserve availability
- use deception and intervention strategically

That is why SentinelDB is hard in the right way. It makes the shortcut failure mode visible instead of hiding it.

---

## Architecture Overview

```text
FastAPI/OpenEnv server
    -> environment reset/step/state
    -> live demo endpoints

SentinelEnvironment
    -> query generation
    -> threat signal extraction
    -> reward computation
    -> policy violation checking

Database targets
    -> real database
    -> decoy database
    -> backup database
```

### Tech Stack

| Layer | Tools |
|---|---|
| Environment | `openenv-core`, pure Python simulation |
| API | `fastapi`, `uvicorn` |
| Models | `pydantic v2` |
| Training | `trl`, `transformers`, `torch` |
| Evaluation | `pandas`, `matplotlib` |
| Tests | `pytest` |
| Packaging | Docker + Space deployment |

---

## Strengths and Current Limits

### Strengths

- deception is a first-class action, not an afterthought
- the benchmark measures a real tradeoff
- reward is deterministic and multi-component
- long-horizon state makes one-step shortcuts insufficient
- the evaluation pipeline is complete and reproducible

### Current Limits

- some lexical threat signals are still brittle
- the attack pool is finite and should become more procedural over time
- the strongest benchmark evidence today is still baseline policy comparison rather than a fully converged learned policy

We think these are acceptable limitations for a hackathon environment because the core benchmark is already doing something valuable: it exposes the hard part of the task clearly.

---

## Reproducing SentinelDB

### 1. Start the environment

```bash
git clone https://github.com/Mady2005/SentinelDB.git
cd SentinelDB
pip install -r requirements.txt
python -m uvicorn server.app:app --port 8001
```

### 2. Run the benchmark

```bash
python evaluate.py --episodes 20 --output-dir submission-metrics
```

### 3. Run the minimal training loop

```bash
python -X utf8 train_trl.py --env-url http://127.0.0.1:8001/openenv --model-name sshleifer/tiny-gpt2 --episodes 4 --output-dir submission-training
```

### 4. Open the live demo

Visit the public Space:

- `https://huggingface.co/spaces/Maddie75/SentinelDB-Train`

### 5. Use the validator-facing notebook

Open the Colab notebook linked from the repository README to run the minimal reproducible training pipeline end-to-end.

---

## Why This Matters

SentinelDB is a proof of concept for a broader class of agent benchmarks: environments where the right policy is not "be maximally permissive" or "be maximally restrictive," but to manage a real operational tradeoff over long sessions.

We think that matters well beyond cybersecurity.

Many real-world agent tasks have the same structure:

- multiple conflicting objectives
- partial observability
- delayed consequences
- strategic interaction with another actor
- reward hacking risks if the environment is oversimplified

SentinelDB is one concrete, practical example of how to build those environments well.

---

## Links

- **Hugging Face Space:** `https://huggingface.co/spaces/Maddie75/SentinelDB-Train`
- **GitHub Repo:** `https://github.com/Mady2005/SentinelDB.git`
- **Colab Notebook:** linked from the repository README

---

*Built for the OpenEnv Hackathon 2025. SentinelDB is our attempt to make long-horizon cyber-defense trainable, inspectable, and hard to game.*
