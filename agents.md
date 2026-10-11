# AGENTS.md
## Tech stack
Python 3.11+, pandas/pyarrow for telemetry, pytest for correctness, pyyaml for config.

## Hard rules
- Never hardcode board/card/agent data in .py files — always read from config/*.yaml.
- Every rules-engine function needs a pytest case before/alongside it (tests/test_rules.py).
- All RNG goes through a per-game seeded `random.Random` instance — never the global `random` module.
- Log atomic events (roll, buy, rent, build, trade, mortgage, bankruptcy), not just per-turn state snapshots.

## Current stage
Stage 1: core rules engine for 3- and 4-player games. Data for most tiles is still PLACEHOLDER in config/board.yaml — do not invent numbers for a null field; leave it null and raise/skip.