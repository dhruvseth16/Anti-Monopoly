"""Parquet I/O for event logs and per-game summaries (pandas + PyArrow)."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from .event_log import events_to_frame


def write_events(events: list[dict], game_id: str, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    events_to_frame(events, game_id).to_parquet(path, index=False, engine="pyarrow")
    return path


def read_events(path: str | Path) -> pd.DataFrame:
    return pd.read_parquet(path, engine="pyarrow")


def summarize_game(engine, winner, seed: int, agents: dict, game_id: str) -> dict:
    """One row per game: the table Stage 5 aggregates for win rates by role / agent."""
    end = next((e for e in reversed(engine.events) if e["event"] == "game_end"), {})
    return {
        "game_id": game_id,
        "seed": seed,
        "mode": engine.game_rules["win_conditions"]["active_game"],
        "num_players": len(engine.players),
        "roles": json.dumps({p.id: p.role for p in engine.players}),
        "agents": json.dumps({pid: a.params.get("id") for pid, a in agents.items()}),
        "winner_id": None if winner is None else winner.id,
        "winner_role": None if winner is None else winner.role,
        "winner_agent": None if winner is None else agents[winner.id].params.get("id"),
        "end_reason": end.get("reason", "unknown"),
        "rounds": engine.turn_count,
        "n_events": len(engine.events),
        "n_bankruptcies": sum(1 for e in engine.events if e["event"] == "bankruptcy"),
        "n_builds": sum(1 for e in engine.events if e["event"] == "build"),
    }


def write_summaries(rows: list[dict], path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_parquet(path, index=False, engine="pyarrow")
    return path
