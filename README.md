---
title: SentinelDB
emoji: 🛡️
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
pinned: false
short_description: Long-horizon cyber defense with budgeted oversight.
---

# SentinelDB

SentinelDB is an OpenEnv environment for **long-horizon cyber defense**. A `Sentinel` agent must protect a real database across long mixed-traffic sessions while preserving availability for legitimate users. A second `Oversight` agent can selectively approve or override risky decisions under a **limited intervention budget**. The result is a multi-agent environment with delayed consequences, partial observability, deception, and explicit security-vs-availability tradeoffs.

This project is designed to score well on the OpenEnv Hackathon because it is not a one-shot classifier or toy regex game. It is a **stateful, trainable environment** with:

- persistent world state
- budgeted multi-agent interaction
- objective, deterministic reward
- visible before/after benchmark signals
- a live Hugging Face Space demo

The repo is pinned to the latest required OpenEnv package line used in the hackathon materials: `openenv-core==0.2.3`.

## Submission Links

- Hugging Face Space: https://huggingface.co/spaces/Maddie75/SentinelDB-Train
- Code Repository: https://github.com/Mady2005/SentinelDB
- Colab Notebook: https://colab.research.google.com/drive/1hKlL3n82yd8K5cfapq2KD2aLZnu9fYDp?usp=sharing
- Mini Blog Draft: [docs/blog.md](docs/blog.md)
- Training Script: [train_trl.py](train_trl.py)
- Training Notebook File: [notebooks/SentinelDB_Training.ipynb](notebooks/SentinelDB_Training.ipynb)
- Submission Writeup: [docs/WRITEUP.md](docs/WRITEUP.md)
- Judge Brief: [docs/JUDGE_BRIEF.md](docs/JUDGE_BRIEF.md)
- Pitch Notes: [docs/PITCH.md](docs/PITCH.md)
- Slides Notes: [docs/SLIDES.md](docs/SLIDES.md)
-job url:[https://huggingface.co/jobs/Maddie75/69ed0433d70108f37acdec21]
Validator note:
- this repo includes a runnable training script
- the public Colab notebook is linked above
- reward and loss plots are committed as `.png` files
- all deliverables are reachable from this README

## Hackathon Requirements Checklist

Minimum submission requirements from the OpenEnv Hackathon are covered as follows:

- **Latest OpenEnv release used**
  This repo is pinned to `openenv-core==0.2.3`.

- **OpenEnv-compliant environment on Hugging Face Spaces**
  Public Space: https://huggingface.co/spaces/Maddie75/SentinelDB-Train

- **Minimal training script using Hugging Face TRL / Colab**
  Notebook: https://colab.research.google.com/drive/1hKlL3n82yd8K5cfapq2KD2aLZnu9fYDp?usp=sharing
  Script: [train_trl.py](train_trl.py)

- **Evidence of real training**
  Committed plots:
  - [submission-training/plots/reward_curve.png](submission-training/plots/reward_curve.png)
  - [submission-training/plots/loss_curve.png](submission-training/plots/loss_curve.png)
  Supporting remote run:
  - https://huggingface.co/jobs/Maddie75/69ed0433d70108f37acdec21

- **Short writeup / blog / presentation material**
  - [docs/blog.md](docs/blog.md)
  - [docs/WRITEUP.md](docs/WRITEUP.md)
  - [docs/SLIDES.md](docs/SLIDES.md)

- **README with problem, environment, and results**
  This file links the Space, repo, notebook, docs, and benchmark outputs in one place.

## Why This Stands Out

### Theme fit

- **Primary theme:** Long-Horizon Planning & Instruction Following
- **Secondary theme:** Multi-Agent Interactions
- **Supporting angle:** World Modeling for professional security workflows

Why this mapping is strong:

- The task is long-horizon: one bad allow can damage future reward for many steps.
- The agent must reason over source history, recent attacks, false positives, and live DB health.
- Oversight creates a real second decision-maker with its own limited budget and intervention policy.
- The environment models a partially observable professional workflow rather than a toy grid or static classification task.

### Judge-facing story

SentinelDB turns a real product tension into a benchmark:

- permissive defenders get compromised
- paranoid defenders block legitimate traffic
- good defenders balance security, availability, deception, and oversight

That gives judges a simple, memorable story with measurable outcomes.

## Environment Overview

### Agent roles

- `Sentinel`: primary defender that proposes one of four actions
- `Oversight`: budgeted reviewer that can approve or override high-risk proposals

### Defender action space

- `ALLOW_REAL`
- `BLOCK`
- `ROUTE_DECOY`
- `BACKUP_ALLOW`

### Oversight action space

- `APPROVE`
- `OVERRIDE_TO_BLOCK`
- `OVERRIDE_TO_DECOY`

### Attacker profiles

- `noob`: noisy and obvious attacks
- `stealth`: mostly benign-looking traffic with subtle escalation
- `aggressive`: bursts of high-risk attack traffic

### Observation includes

- raw query text
- lexical risk flags
- per-source history
- recent blocked and successful attacks
- recent false positives
- real DB health
- decoy mode
- allowed attack/false-positive constraints

## Why It Is Not a Toy Environment

The most common RL environment failure is making verification easy but unrealistic. SentinelDB explicitly tries to avoid that.

### What we do deliberately

- **No LLM-as-judge reward core**
  Reward comes from deterministic environment outcomes, not a model judge.

- **Multiple reward components**
  Reward is not a single scalar hack target. It is decomposed into:
  - security
  - availability
  - deception
  - oversight
  - operational penalties

- **Persistent consequences**
  Attack success changes DB health and future trajectories; this is not a one-turn scoring trick.

- **Operational failure modes**
  The environment now includes realistic enterprise-style signals such as:
  - permission risk
  - schema mismatch risk
  - timeout pressure
  - rate-limit pressure

- **Constrained action space**
  The policy cannot exploit arbitrary tool calls or hidden code execution.

### Pitfalls we explicitly address

- Weak verifiers: mitigated by deterministic multi-signal environment reward
- Reward hacking: mitigated by constrained actions, bounded episodes, and multiple tracked metrics
- Overly toy abstraction: mitigated by stateful sessions, decoy routing, DB health, and operational failure modes
- One-scalar evaluation: mitigated by reporting attack success, false positives, and return together

## Reward Design

SentinelDB is optimized for the **security-availability tradeoff**, not just attack blocking.

### Core reward terms

- serve benign traffic: `+1.0`
- false positive: `-0.5`
- blocked attack: `+0.5`
- decoy-routed attack: `+0.6`
- attack allowed through: `-5.0`
- compromise terminal penalty: `-10.0`
- backup use: `-0.2`
- oversight intervention cost: `-0.1`
- correct high-value override: `+1.0`
- wrong override on benign traffic: `-0.4`

### Reward interpretation

This means a policy cannot win by:

- allowing everything
- blocking everything
- overusing oversight

The intended optimum is a balanced policy that keeps attack success low **without** collapsing into `100%` false positives.

## Training Evidence

The required training artifacts are committed in the repo as image files.

### Reward Curve

![Reward curve](submission-training/plots/reward_curve.png)

Caption: reward changes over training episodes in the GRPO training pipeline.

### Loss Curve

![Loss curve](submission-training/plots/loss_curve.png)

Caption: training loss from the same run, committed as a validator-visible artifact.

### Benchmark Curves

![Episode return benchmark](final-oversight-metrics/plots/episode_return.png)

![Attack success benchmark](final-oversight-metrics/plots/attack_success_rate.png)

### Training Deliverables For Judges

The main training deliverables for this submission are:

- the public Colab notebook
- the runnable [train_trl.py](train_trl.py) script
- committed validator-visible plot files in this repo

Additional onsite compute-backed evidence:

- Hugging Face Job: https://huggingface.co/jobs/Maddie75/69ed0433d70108f37acdec21

Important note:

- the HF Job URL is supporting evidence only
- the primary training submission artifacts are the notebook, script, and committed `.png` plots

## Results That Matter

Judges care more about behavioral tradeoffs than raw loss. These are the metrics that matter most in SentinelDB:

- `episode_return`
- `attack_success_rate`
- `false_positive_rate`
- oversight usefulness

### Current benchmark snapshot

From [final-oversight-metrics/summary.json](final-oversight-metrics/summary.json):

| Policy | Avg Return | Attack Success | False Positive |
| --- | ---: | ---: | ---: |
| `heuristic_guarded` | `80.1167` | `0.0` | `0.0` |
| `heuristic` | `79.7933` | `0.0` | `0.0` |
| `always_block` | `-1.0667` | `0.0` | `1.0` |
| `always_allow` | `-18.6667` | `1.0` | `0.0` |

Takeaway:

- permissive policies fail security
- over-defensive policies fail usability
- balanced policies dominate

That is exactly the behavior we want the trained policy to learn.

### Diagnostic benchmark reporting

SentinelDB now reports benchmark performance at three levels:

- overall policy return and error rates
- attacker-profile slices
- scenario-level slices

Scenario labels include:

- `benign_read`
- `benign_write`
- `operational_anomaly`
- `privilege_escalation`
- `sql_injection`
- `exfiltration`
- `destructive_ddl`

This makes the benchmark more diagnostic than a single average score. Judges can inspect not just whether a policy wins overall, but **what kinds of situations it handles well or poorly**.

## What Improved

The most important learning signal in SentinelDB is not "block more." It is **improve the security-availability tradeoff**.

What our current evidence already shows:

- the environment strongly separates bad policies from good ones
- permissive behavior leads to compromise
- paranoid behavior leads to unusable false-positive rates
- balanced policies achieve high return without sacrificing safety

What the training pipeline is designed to improve:

- keep `attack_success_rate` low
- avoid collapse into `false_positive_rate = 1.0`
- increase `episode_return` by learning when to allow, block, deceive, or escalate to oversight

Why this matters:

- reward curves alone are not enough
- SentinelDB is valuable because it makes the correct policy non-trivial
- a model can appear "safe" by blocking too aggressively, but that is a failure in this environment

So the real improvement target is:

- **lower attack success without destroying availability**

That is the behavior we want a trained policy to learn, and it is the core reason this environment is useful for OpenEnv-style post-training.

## OpenEnv Compliance

- Manifest: [openenv.yaml](openenv.yaml)
- Pydantic action and observation models: [sentineldb_env/models.py](sentineldb_env/models.py)
- FastAPI OpenEnv wrapper: [server/app.py](server/app.py)
- Gym-style reset / step / state: [server/sentinel_environment.py](server/sentinel_environment.py)

The environment is OpenEnv-compatible and hosted on Hugging Face Spaces as required by the hackathon.

## Demo Experience

Start the API and open `/demo`. The interface shows:

- Sentinel proposal
- Oversight decision
- Final executed action
- risk score and rationale
- suspicious signals and failure modes
- reward breakdown
- real DB versus decoy routing
- live resilience/session metrics
- timeline updates across a persistent story

### Recommended demo sequence

1. benign read to show availability is preserved
2. injection or exfiltration attempt to show defensive action
3. destructive query to show critical response
4. multi-step sequence to show long-horizon state updates

## Training Pipeline

The included [train_trl.py](train_trl.py) is a GRPO-based training scaffold connected to the environment.

It:

1. builds prompts from `SentinelObservation`
2. runs rollouts through the OpenEnv HTTP client
3. computes deterministic environment reward
4. saves validator-friendly plots and summaries

Example:

```bash
python -X utf8 train_trl.py --env-url http://localhost:8001/openenv --episodes 16 --output-dir submission-training
```

Important training note:

- a strong result in SentinelDB is **not** “block everything”
- a strong result is low attack success **and** low false positives

That tradeoff is the real learning target.

## Evaluation

Use the evaluation script to compare baselines and generate plots:

```bash
python evaluate.py --env-url http://localhost:8001/openenv --episodes 20 --output-dir final-oversight-metrics
```

This saves:

- `metrics.csv`
- `scenario_metrics.csv`
- `summary.json`
- `profile_summary.json`
- `scenario_summary.json`
- `plots/attack_success_rate.png`
- `plots/episode_return.png`

## Local Setup

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
pytest
uvicorn server.app:app --reload --port 8001
```

On Windows:

```bat
run_demo.bat
```

The OpenEnv endpoints are available at `http://localhost:8001/openenv`.

## Docker

```bash
docker build -t sentineldb-env .
docker run --rm -p 7860:7860 sentineldb-env
```

## Project Structure

```text
newUpdated/
|-- sentineldb_env/
|   |-- __init__.py
|   |-- client.py
|   `-- models.py
|-- server/
|   |-- app.py
|   |-- sentinel_environment.py
|   `-- static/index.html
|-- tests/
|   `-- test_environment.py
|-- notebooks/
|   `-- SentinelDB_Training.ipynb
|-- docs/
|   |-- blog.md
|   |-- JUDGE_BRIEF.md
|   |-- PITCH.md
|   |-- SLIDES.md
|   `-- WRITEUP.md
|-- train_trl.py
|-- evaluate.py
|-- evaluate_model.py
|-- openenv.yaml
|-- Dockerfile
`-- README.md
```

## Final Judge Takeaway

SentinelDB is a reusable OpenEnv benchmark for **long-horizon, partially observable, multi-agent cyber defense**. It stands out because it combines:

- realistic sequential security tradeoffs
- budgeted oversight
- decoy-based deception
- deterministic reward
- committed training evidence
- a fast, memorable live demo

This is not just a classifier wrapped in a UI. It is a trainable environment built to improve LLM decision-making on a difficult real-world tradeoff.
