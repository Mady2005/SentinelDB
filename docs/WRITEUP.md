# SentinelDB Submission Writeup

## One-line summary

SentinelDB is an OpenEnv-ready long-horizon cyber-defense environment where a `Sentinel` agent protects a real database while a budgeted `Oversight` agent reviews risky actions before execution.

## Problem statement

Production databases face mixed traffic over time: benign reads, stealthy probing, exfiltration attempts, and destructive commands can all appear in the same session. A useful defender must preserve availability for legitimate users while preventing compromise of the real system. SentinelDB turns that tension into a sequential decision problem with delayed consequences, partial observability, and persistent environment state.

## Why this environment is useful for LLM training

- It is stepwise rather than one-shot.
- It has objective rule-based rewards.
- It has persistent state across long episodes.
- It includes explicit multi-agent interaction:
  - `Sentinel` proposes the defense action.
  - `Oversight` can approve or override under a fixed intervention budget.

## Environment design

- Observation includes query text, lexical threat flags, source history, recent blocked and successful attacks, false positives, and database health.
- Defender action space:
  - `ALLOW_REAL`
  - `BLOCK`
  - `ROUTE_DECOY`
  - `BACKUP_ALLOW`
- Oversight action space:
  - `APPROVE`
  - `OVERRIDE_TO_BLOCK`
  - `OVERRIDE_TO_DECOY`
- Episode length: up to 100 steps.
- Attacker profiles: `noob`, `stealth`, and `aggressive`.

## Reward and verifier logic

The environment uses verifiable rule-based rewards rather than a learned reward model.

- Serve benign traffic: `+1.0`
- False positive: `-0.5`
- Block attack: `+0.5`
- Route attack to decoy: `+0.6`
- Allow attack through: `-5.0`
- Compromise terminal penalty: `-10.0`
- Backup use: `-0.2`
- Oversight intervention cost: `-0.1`
- Correct high-value override: `+1.0`
- Wrong override on benign traffic: `-0.4`

## Safeguards against reward hacking

- Fixed action space with constrained parsing
- Bounded episode length
- No arbitrary code execution inside the environment loop
- Multiple tracked metrics beyond total reward
- Oversight budget prevents unlimited intervention exploits

## Training stack

- OpenEnv-compatible FastAPI environment
- TRL `GRPOTrainer`
- Notebook and script paths included in the repo
- Training artifacts committed as `.png` files for validator checks

## Current results

From `final-oversight-metrics/summary.json` over 30 episodes:

- `heuristic_guarded`: return `80.1167`, attack success `0.0`, false positive `0.0`
- `heuristic`: return `79.7933`, attack success `0.0`, false positive `0.0`
- `always_block`: return `-1.0667`, attack success `0.0`, false positive `1.0`
- `always_allow`: return `-18.6667`, attack success `1.0`, false positive `0.0`

## Demo story

The demo makes the two-agent interaction visible:

1. A query enters the system.
2. `Sentinel` proposes the action.
3. `Oversight` approves or overrides.
4. The final action hits the real DB, gets blocked, or goes to the decoy.
5. Session metrics and the timeline update live.

## Deliverables in this repo

- Environment manifest: `openenv.yaml`
- Demo server: `server/app.py`
- Environment logic: `server/sentinel_environment.py`
- Training script: `train_trl.py`
- Training notebook file: `notebooks/SentinelDB_Training.ipynb`
- Training plots:
  - `submission-training/plots/loss_curve.png`
  - `submission-training/plots/reward_curve.png`
