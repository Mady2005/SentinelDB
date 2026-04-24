# SentinelDB 3-Minute Pitch

## Opening

Databases face two opposing risks: let too much through and you get compromised, block too much and you break the product. SentinelDB turns that tradeoff into a long-horizon OpenEnv benchmark where an LLM defender must protect a real database while keeping legitimate traffic flowing.

## Problem

Most security demos only show static classification. Real defenders operate over sequences: sources build history, attacks arrive in bursts, and a single wrong allow can silently damage the system. That makes database defense a strong fit for OpenEnv and RL.

## Environment

SentinelDB has three attacker profiles: `noob`, `stealth`, and `aggressive`. On every step, the Sentinel agent sees the current query, source history, recent blocked and successful attacks, false positives, and real DB health. It chooses one of four actions:

- `ALLOW_REAL`
- `BLOCK`
- `ROUTE_DECOY`
- `BACKUP_ALLOW`

This is where the environment innovation comes from: the agent is not just filtering traffic, it can also deceive attackers with a decoy database and protect availability at the same time.

## Benchmark Result

We benchmarked three policies over 50 episodes:

- `always_allow`: average return `-19.22`, attack success `100%`
- `always_block`: average return `-4.96`, false positive rate `100%`
- `heuristic Sentinel`: average return `81.66`, attack success `0%`, false positives `0%`

That gives a clear story: permissive policies lose security, paranoid policies lose availability, and balanced policies win on both.

## Learned Policy

We also wired SentinelDB into TRL GRPO with the latest OpenEnv-compatible rollout pattern. A small instruct model can be trained directly against the environment and evaluated with the same metrics, which makes SentinelDB reusable as both a benchmark and a training pipeline.

## Demo

In the live demo, I’ll show three queries:

1. Benign query goes to the real database.
2. Exfiltration query gets blocked or routed away.
3. Destructive query is immediately stopped, preserving the real database.

The UI shows the Watcher, Analyzer, Defender, Deception, and Migration logs so judges can follow the agent’s decision in one glance.

## Close

SentinelDB is a realistic, reusable OpenEnv benchmark for cyber defense. It combines multi-agent pressure, long-horizon planning, deception, and measurable reward tradeoffs in a format any LLM policy can plug into.

