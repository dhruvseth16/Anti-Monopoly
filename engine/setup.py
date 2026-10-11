"""Role assignment and starting setup — Rules 4, 5, 6.

The one piece of real, working logic in stage 1 — fully specified by the rulebook,
independent of the still-missing title card data.
"""
import random

from .player import Player


def assign_roles(num_players: int, rng: random.Random) -> list[str]:
    """
    Rule 4 role-balance rule:
      - even player count -> exactly half competitors, half monopolists
      - odd player count  -> counts differ by at most 1
    Returns one role per seat, shuffled so no seat index is biased toward either role.
    """
    if num_players < 2 or num_players > 6:
        raise ValueError("Anti-Monopoly supports 2-6 players")

    half = num_players // 2
    if num_players % 2 == 0:
        n_competitors = half
    else:
        # odd count: split is half / half+1 either way — pick randomly which role gets the extra seat
        n_competitors = half if rng.random() < 0.5 else half + 1

    roles = ["competitor"] * n_competitors + ["monopolist"] * (num_players - n_competitors)
    rng.shuffle(roles)
    return roles


def starting_cash_total(game_rules: dict) -> int:
    return game_rules["starting_cash"]["total"]


def create_players(num_players: int, rng: random.Random, game_rules: dict) -> list[Player]:
    roles = assign_roles(num_players, rng)
    cash = starting_cash_total(game_rules)
    return [Player(id=i, role=role, cash=cash) for i, role in enumerate(roles)]
