import random
from pathlib import Path

import pytest
import yaml

from engine.setup import assign_roles, create_players

GAME_RULES = yaml.safe_load(Path("config/game_rules.yaml").read_text())


def test_four_player_role_balance_is_exactly_even():
    roles = assign_roles(4, random.Random(42))
    assert roles.count("competitor") == 2
    assert roles.count("monopolist") == 2


def test_three_player_role_balance_differs_by_at_most_one():
    roles = assign_roles(3, random.Random(42))
    diff = abs(roles.count("competitor") - roles.count("monopolist"))
    assert diff <= 1


def test_seeded_role_assignment_is_reproducible():
    roles_a = assign_roles(4, random.Random(7))
    roles_b = assign_roles(4, random.Random(7))
    assert roles_a == roles_b


def test_invalid_player_counts_rejected():
    with pytest.raises(ValueError):
        assign_roles(1, random.Random(1))
    with pytest.raises(ValueError):
        assign_roles(7, random.Random(1))


def test_starting_cash_matches_rulebook():
    players = create_players(4, random.Random(1), GAME_RULES)
    assert all(p.cash == 1500 for p in players)


def test_pawn_color_matches_role():
    players = create_players(4, random.Random(1), GAME_RULES)
    for p in players:
        expected = "green" if p.role == "competitor" else "blue"
        assert p.pawn_color == expected
