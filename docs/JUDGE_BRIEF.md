# SentinelDB Judge Brief

## One-line summary

SentinelDB is an OpenEnv-ready long-horizon cyber-defense environment where a `Sentinel` agent protects a real database while a budgeted `Oversight` agent reviews risky decisions before execution.

## Theme positioning

- Primary theme: `Long-Horizon Planning & Instruction Following`
- Secondary theme: `Multi-Agent Interactions`
- Bonus framing: `Scalable Oversight`

## Problem statement

Modern databases do not fail because of one isolated bad query. They fail because defenders must manage mixed traffic over time: benign traffic, stealthy probing, exfiltration attempts, and destructive actions all arrive in sequence. SentinelDB turns that into a sequential decision problem with delayed penalties, partial observability, and persistent world state.

## Why it is competitive

- It is a true environment, not a one-step classifier.
- It combines security and availability in the same reward function.
- It has visible long-horizon state: DB health, source history, recent attack outcomes, and decoy engagement.
- It now exposes real multi-agent structure:
  - `Sentinel` proposes an action
  - `Oversight` can approve or override under a limited intervention budget
- It already has a deployable demo, benchmark pipeline, Hugging Face Space, and TRL training script.

## Core agent workflow

1. The environment produces an observation containing the current query, lexical risk flags, source history, recent attack outcomes, and current DB health.
2. The `Sentinel` agent proposes one of:
   - `ALLOW_REAL`
   - `BLOCK`
   - `ROUTE_DECOY`
   - `BACKUP_ALLOW`
3. The `Oversight` agent sees the proposed action plus the risk summary and remaining budget.
4. Oversight either:
   - `APPROVE`
   - `OVERRIDE_TO_BLOCK`
   - `OVERRIDE_TO_DECOY`
5. The final action is executed and the environment updates persistent state.

## Reward logic

- Serve benign traffic: `+1.0`
- False positive on benign traffic: `-0.5`
- Block attack: `+0.5`
- Route attack to decoy: `+0.6`
- Allow attack through: `-5.0`
- Terminal compromise: `-10.0`
- Backup use: `-0.2`
- Terminal decoy engagement bonus: `+0.1 * decoy_engagement`
- Oversight intervention cost: `-0.1`
- Correct high-value override: `+1.0`
- Wrong override on benign traffic: `-0.4`

## Fresh benchmark result

From [final-oversight-metrics/summary.json](</C:/Users/madhu/OneDrive/Documents/New project/sentineldb-submission-updated/final-oversight-metrics/summary.json:1>) over 30 episodes:

- `heuristic_guarded`: return `80.12`, attack success `0%`, false positives `0%`
- `heuristic`: return `79.79`, attack success `0%`, false positives `0%`
- `always_block`: return `-1.07`, attack success `0%`, false positives `100%`
- `always_allow`: return `-18.67`, attack success `100%`, false positives `0%`

Judge takeaway:
- permissive policies fail security
- over-defensive policies fail usability
- balanced policies dominate
- oversight keeps the environment genuinely multi-agent even when it intervenes sparingly

## Training readiness

Local rehearsal completed successfully:

- End-to-end GRPO/TRL smoke training completed with a cached tiny model:
  - output: [rehearsal-train/rollout_summary.csv](</C:/Users/madhu/OneDrive/Documents/New project/sentineldb-submission-updated/rehearsal-train/rollout_summary.csv:1>)
- Pre/post evaluation artifacts were generated:
  - before: [rehearsal-model-before/model_summary.json](</C:/Users/madhu/OneDrive/Documents/New project/sentineldb-submission-updated/rehearsal-model-before/model_summary.json:1>)
  - after: [rehearsal-model-after/model_summary.json](</C:/Users/madhu/OneDrive/Documents/New project/sentineldb-submission-updated/rehearsal-model-after/model_summary.json:1>)

Important note:
- the local rehearsal proves the training pipeline works
- it is not the final improvement claim
- the final reward-improvement proof should be generated onsite with a stronger model and more episodes

## What to show live

1. Open the Hugging Face Space demo.
2. Show the relay UI:
   - Sentinel proposal
   - Oversight decision
   - Final executed action
3. Run a benign query to show usefulness is preserved.
4. Run an exfiltration or destructive query to show risk signals and safe intervention.
5. Run the multi-step attack story to show the long-horizon board updating:
   - DB health
   - attack success rate
   - false positive rate
   - oversight budget
   - timeline

## Judge takeaway

SentinelDB is a reusable OpenEnv benchmark for long-horizon, partially observable, multi-agent cyber defense. It is easy to demo, easy to score, and realistic enough to support actual training rather than one-shot prompt tricks.
