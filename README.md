---
title: SentinelDB
emoji: 🛡️
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
pinned: false
short_description: Cyber defense demo with budgeted oversight.
---

# SentinelDB

SentinelDB is an OpenEnv-ready cyber defense environment where a `Sentinel` agent protects a real database from a long stream of benign and adversarial queries while a budgeted `Oversight` agent reviews high-risk choices before execution. The core tension is security versus availability: blocking attacks helps, but blocking legitimate traffic hurts the reward, and routing suspicious traffic to a decoy database creates delayed upside.

The repo is pinned to the current official OpenEnv core distribution: `openenv-core==0.2.3`. The package name changed, but the Python imports still use `openenv`.

## Submission Links

- Hugging Face Space: https://huggingface.co/spaces/Maddie75/SentinelDB
- Code Repository: https://huggingface.co/spaces/Maddie75/SentinelDB/tree/main
- Training Script: [train_trl.py](train_trl.py)
- Colab Notebook: https://colab.research.google.com/drive/1hKlL3n82yd8K5cfapq2KD2aLZnu9fYDp?usp=sharing
- Training Notebook File: [notebooks/SentinelDB_Training.ipynb](notebooks/SentinelDB_Training.ipynb)
- Submission Writeup: [docs/WRITEUP.md](docs/WRITEUP.md)
- Judge Brief: [docs/JUDGE_BRIEF.md](docs/JUDGE_BRIEF.md)
- Pitch Notes: [docs/PITCH.md](docs/PITCH.md)
- Slides Notes: [docs/SLIDES.md](docs/SLIDES.md)

Note: the validator accepts a runnable training script, and this repo includes both a Python training script and a notebook file. The public Colab link above is the submission-ready hosted notebook version.

## Training Evidence

The required training artifacts are committed to the repo as image files.

### Reward Curve

![Reward curve](submission-training/plots/reward_curve.png)

### Loss Curve

![Loss curve](submission-training/plots/loss_curve.png)

### Benchmark Curves

![Episode return benchmark](final-oversight-metrics/plots/episode_return.png)

![Attack success benchmark](final-oversight-metrics/plots/attack_success_rate.png)

## Why this fits the hackathon

- Primary theme: `Long-Horizon Planning & Instruction Following`
- Secondary theme: `Multi-Agent Interactions`
- Bonus framing: `Scalable Oversight`
- Environment innovation: cyber deception and database defense are uncommon OpenEnv benchmark themes.
- Storytelling: the setup is visual and fast to explain with a Sentinel agent, an Oversight agent, a real DB, and a decoy DB.
- Reward improvement: scripted baselines already show the tradeoff between permissive, over-defensive, and balanced policies.
- Pipeline: the repo includes a minimal OpenEnv HTTP server, a TRL GRPO training script, and an evaluation script.

## Project structure

```text
sentineldb-submission-updated/
|-- sentineldb_env/
|   |-- __init__.py
|   |-- client.py
|   `-- models.py
|-- server/
|   |-- app.py
|   `-- sentinel_environment.py
|-- tests/
|   `-- test_environment.py
|-- notebooks/
|   `-- SentinelDB_Training.ipynb
|-- docs/
|   |-- JUDGE_BRIEF.md
|   |-- PITCH.md
|   `-- SLIDES.md
|-- train_trl.py
|-- evaluate.py
|-- openenv.yaml
|-- Dockerfile
`-- README.md
```

## Environment design

- Episode length: up to 100 steps.
- Attacker profiles:
  - `noob`: frequent obvious attacks.
  - `stealth`: mostly benign traffic with subtle exfiltration or injection attempts.
  - `aggressive`: bursts of high-risk attack traffic with cooldown periods.
- Defender actions:
  - `ALLOW_REAL`
  - `BLOCK`
  - `ROUTE_DECOY`
  - `BACKUP_ALLOW`
- Oversight actions:
  - `APPROVE`
  - `OVERRIDE_TO_BLOCK`
  - `OVERRIDE_TO_DECOY`
- Observation:
  - current query text and lexical risk flags
  - per-source history
  - recent blocked attacks, successful attacks, and false positives
  - real DB health and decoy mode
  - remaining oversight budget
- Reward:
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

## OpenEnv compliance

- Parseable environment manifest: [openenv.yaml](openenv.yaml)
- Pydantic action and observation models: [sentineldb_env/models.py](sentineldb_env/models.py)
- FastAPI OpenEnv wrapper: [server/app.py](server/app.py)
- Gym-style environment logic with reset/step/state: [server/sentinel_environment.py](server/sentinel_environment.py)

## Local setup

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
pytest
uvicorn server.app:app --reload --port 8001
```

On Windows, you can also use the included one-click launcher:

```bat
run_demo.bat
```

The OpenEnv-compatible endpoints are available at `http://localhost:8001/openenv`.

If you prefer installing manually, use:

```bash
pip install openenv-core==0.2.3
```

## Docker

```bash
docker build -t sentineldb-env .
docker run --rm -p 7860:7860 sentineldb-env
```

## Live demo

Start the API and open [http://localhost:8001/demo](http://localhost:8001/demo). The page shows:

- Sentinel proposal
- Oversight decision
- Final executed action
- risk score and rationale
- threat level
- real DB versus decoy routing
- resilience metrics across a persistent session
- session timeline for a judge-friendly long-horizon story

## Training with TRL

The included [train_trl.py](train_trl.py) is a minimal GRPO scaffold designed for the hackathon. It does four things:

1. Builds prompts from `SentinelObservation`.
2. Runs environment rollouts through the OpenEnv HTTP client.
3. Writes rollout reward summaries.
4. Writes validator-friendly image artifacts:
   - `plots/reward_curve.png`
   - `plots/loss_curve.png`

Example:

```bash
python -X utf8 train_trl.py --env-url http://localhost:8001/openenv --episodes 16 --output-dir submission-training
```

Notes:

- Keep the first run small. Judges care more about clear reward improvement than large-scale training.
- If you switch to Unsloth, keep the same prompt and reward logic and just swap the trainer section.
- On Windows, `-X utf8` avoids a TRL import issue caused by the default code page.

## Evaluation

Use the evaluation script to compare simple baselines and create plots:

```bash
python evaluate.py --env-url http://localhost:8001/openenv --episodes 20 --output-dir final-oversight-metrics
```

This saves:

- `final-oversight-metrics/metrics.csv`
- `final-oversight-metrics/summary.json`
- `final-oversight-metrics/plots/attack_success_rate.png`
- `final-oversight-metrics/plots/episode_return.png`

Current benchmark summary from [final-oversight-metrics/summary.json](final-oversight-metrics/summary.json):

- `heuristic_guarded`: return `80.1167`, attack success `0.0`, false positive `0.0`
- `heuristic`: return `79.7933`, attack success `0.0`, false positive `0.0`
- `always_block`: return `-1.0667`, attack success `0.0`, false positive `1.0`
- `always_allow`: return `-18.6667`, attack success `1.0`, false positive `0.0`

## Judge package

If you are preparing the final submission, start with:

- [docs/JUDGE_BRIEF.md](docs/JUDGE_BRIEF.md)
- [docs/PITCH.md](docs/PITCH.md)
- [docs/SLIDES.md](docs/SLIDES.md)

## Demo ideas

- Benign query gets `ALLOW_REAL`.
- Obvious injection gets `BLOCK`.
- Repeated suspicious source gets `ROUTE_DECOY`.
- A high-risk allow proposal gets caught by oversight.
