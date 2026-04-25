# SentinelDB 3-Minute Pitch

## Opening

Databases face two opposing risks: let too much through and you get compromised, block too much and you break the product. SentinelDB turns that tension into a long-horizon OpenEnv benchmark where an LLM defender must protect a real database while keeping legitimate traffic flowing.

## Problem

Most security demos only show static classification. Real defenders operate over sequences: sources build history, attacks arrive in bursts, and a single wrong allow can silently damage the system. That makes database defense a strong fit for OpenEnv and reinforcement learning.

## Environment

SentinelDB has three attacker profiles: `noob`, `stealth`, and `aggressive`. On every step, the Sentinel agent sees the current query, source history, recent blocked and successful attacks, false positives, and live database health. It chooses one of four actions:

- `ALLOW_REAL`
- `BLOCK`
- `ROUTE_DECOY`
- `BACKUP_ALLOW`

A second `Oversight` agent can approve or override risky decisions under a limited intervention budget. That makes the environment both multi-agent and long-horizon: decisions change future state, not just the current step.

## Benchmark Result

We benchmarked three core policies:

- `always_allow`: compromised quickly and fails security
- `always_block`: keeps attack success low but produces unusable false positives
- `heuristic Sentinel`: high return with low attack success and low false positives

That gives a clear story: permissive policies lose security, paranoid policies lose availability, and balanced policies win on both.

## Learned Policy

We also wired SentinelDB into TRL GRPO with an OpenEnv-compatible rollout loop. A small instruct model can be trained directly against the environment and evaluated with the same metrics, which makes SentinelDB reusable as both a benchmark and a post-training pipeline.

The key training lesson is that SentinelDB is hard in the right way. A naive defender can reduce attack success by blocking too aggressively, but that collapses availability and destroys total return. So the real learning target is:

- keep attack success low
- avoid false-positive collapse
- improve episode return over long sessions

That is why we evaluate reward together with attack success rate and false positive rate, instead of looking at loss alone.

## Demo

In the live demo, I'll show three queries:

1. A benign query goes to the real database.
2. A suspicious or exfiltration-style query gets blocked or routed away.
3. A destructive query is stopped immediately, preserving the real database.

The UI makes the full chain visible:

- Sentinel proposal
- Oversight decision
- final executed action
- reward breakdown
- failure modes
- long-horizon session state

## Close

SentinelDB is a realistic, reusable OpenEnv benchmark for cyber defense. It combines multi-agent oversight, long-horizon planning, deception, and measurable reward tradeoffs in a format that can actually be trained on, not just demoed.
