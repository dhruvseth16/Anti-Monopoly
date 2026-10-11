"""Role-specific math: rent, income tax, utility/transport fares, foundation — Rules 9-21.

Stage 1 leaves these as signatures only. tests/test_rules.py already encodes the
expected numbers from the rulebook and the digitized cards, as a correctness target.
"""
from __future__ import annotations

from .player import Player
from .property import PropertyTile, TransportTile, UtilityTile


def rent_due(tile: PropertyTile, owner: Player) -> int:
    raise NotImplementedError  # stage 2: Rules 9, 10, 11 — incl. monopolized-unbuilt doubling


def transport_fare(tile: TransportTile, owner: Player, board) -> int:
    raise NotImplementedError  # stage 2: Rule 19


def utility_charge(tile: UtilityTile, owner: Player, board, dice_roll: int) -> int:
    raise NotImplementedError  # stage 2: Rule 20


def income_tax_due(player: Player, board, rules_config: dict) -> int:
    raise NotImplementedError  # stage 2: Rule 17 — min(flat, role-specific percentage formula)


def foundation_effect(player: Player, rng, rules_config: dict) -> int:
    raise NotImplementedError  # stage 2: Rule 21
