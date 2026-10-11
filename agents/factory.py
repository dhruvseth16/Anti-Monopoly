"""Builds {player_id: agent} from config/agents.yaml, matching profiles to players by role."""
from pathlib import Path

import yaml

from .heuristic_agent import HeuristicAgent


def load_agents(players, config_path: str = "config/agents.yaml") -> dict:
    profiles = yaml.safe_load(Path(config_path).read_text())
    pool = {"competitor": [], "monopolist": []}
    for prof in profiles:
        pool[prof["role"]].append(prof)
    used = {"competitor": 0, "monopolist": 0}
    agents = {}
    for pl in players:
        if used[pl.role] >= len(pool[pl.role]):
            raise ValueError(f"agents.yaml has no free {pl.role} profile for player {pl.id}")
        prof = pool[pl.role][used[pl.role]]
        used[pl.role] += 1
        agents[pl.id] = HeuristicAgent(pl.id, prof)
    return agents
