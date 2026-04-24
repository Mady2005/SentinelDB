# SentinelDB Slide Copy

## Slide 1 - Title

SentinelDB  
OpenEnv benchmark for long-horizon database defense

Tagline: Protect the real DB, preserve normal traffic, and deceive attackers with a decoy.

## Slide 2 - Problem

Modern databases face mixed traffic:

- benign product queries
- stealthy exfiltration attempts
- destructive commands

Static detection is not enough. Defenders need sequential decision-making under uncertainty.

## Slide 3 - Environment

Observation:

- current query text
- suspicious lexical flags
- source history
- recent attacks blocked or successful
- false positives
- real DB health

Actions:

- `ALLOW_REAL`
- `BLOCK`
- `ROUTE_DECOY`
- `BACKUP_ALLOW`

## Slide 4 - Why It’s Novel

- Long-horizon cyber defense instead of one-step classification
- Multi-agent pressure through diverse attacker profiles
- Deception through a decoy database
- Explicit tradeoff between security and availability

## Slide 5 - Reward Design

- serve legitimate traffic: positive reward
- block legitimate traffic: mild penalty
- allow attack to hit real DB: large penalty
- compromise: terminal penalty
- decoy engagement: terminal bonus

Goal: maximize safety without destroying usability.

## Slide 6 - Benchmark Results

50-episode evaluation:

- Heuristic Sentinel: return `81.66`, attack success `0%`, false positives `0%`
- Always Block: return `-4.96`, attack success `0%`, false positives `100%`
- Always Allow: return `-19.22`, attack success `100%`, false positives `0%`

Takeaway: the environment rewards balanced defense, not paranoia or permissiveness.

## Slide 7 - Training Stack

- OpenEnv HTTP environment
- FastAPI server
- TRL GRPO training loop
- evaluation scripts and plot generation

This makes SentinelDB both a benchmark and a trainable environment.

## Slide 8 - Live Demo

Show:

1. benign read allowed on the real DB
2. exfiltration query blocked
3. destructive query blocked or routed away

Narration: Watcher -> Analyzer -> Defender -> Deception -> Migration

## Slide 9 - Closing

SentinelDB is a reusable OpenEnv benchmark for cyber defense with:

- realistic tradeoffs
- strong storytelling
- measurable reward differences
- a clean training pipeline
