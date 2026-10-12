"""Builds one fully-wired game from a seed. Shared by run_single_game (stage 3) and Monte Carlo (stage 4)."""
from __future__ import annotations

import copy
import random
from pathlib import Path

import yaml

from agents.factory import load_agents
from engine.board import Board
from engine.deck import Deck
from engine.engine import Engine
from engine.setup import create_players
from engine.treasurer import Treasurer
from .placeholder_fill import fill_placeholders


def load_game_rules(config_dir: str = "config") -> dict:
    return yaml.safe_load(Path(config_dir, "game_rules.yaml").read_text())


def build_game(seed: int, num_players: int = 4, config_dir: str = "config",
               mode: str | None = None, placeholder_fill: bool = False):
    """Returns (engine, agents). Every random draw (roles, deck shuffles, dice) comes from ONE seeded rng."""
    rules = load_game_rules(config_dir)
    if mode:
        rules = copy.deepcopy(rules)
        rules["win_conditions"]["active_game"] = mode
    rng = random.Random(seed)
    players = create_players(num_players, rng, rules)
    board = Board(str(Path(config_dir, "board.yaml")))
    if placeholder_fill:
        fill_placeholders(board)
    engine = Engine(
        players, board,
        Deck(str(Path(config_dir, "competitor_cards.yaml")), rng),
        Deck(str(Path(config_dir, "monopolist_cards.yaml")), rng),
        Treasurer(rules["bank_denominations"]), rng, rules,
    )
    agents = load_agents(players, str(Path(config_dir, "agents.yaml")))
    return engine, agents
