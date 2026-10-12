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
        if not pool[pl.role]:
            raise ValueError(f"agents.yaml has no {pl.role} profile")
        prof = pool[pl.role][used[pl.role] % len(pool[pl.role])]      # profiles repeat for 5-6 player games
        used[pl.role] += 1
        agents[pl.id] = HeuristicAgent(pl.id, prof)
    return agents
