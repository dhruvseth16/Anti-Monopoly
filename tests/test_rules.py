"""Stage 2: real assertions for engine/rules.py (replaces the stage-1 xfail skeleton)."""
import pytest

from engine.errors import MissingDataError
from engine.player import Player
from engine.property import TransportTile, UtilityTile
from engine import rules
from tests.helpers import RULES, FakeRng, basin, french, own, small_board


def P(role, cash=1500, pid=0): return Player(id=pid, role=role, cash=cash)


def test_basin_street_competitor_rent_no_houses():
    b = small_board(); c = P("competitor"); own(c, b.tile_at(1))
    assert rules.rent_due(b.tile_at(1), c, b, RULES) == 6


def test_basin_street_monopolist_rent_doubles_once_monopolized():
    b = small_board(); m = P("monopolist")
    own(m, b.tile_at(1))
    assert rules.rent_due(b.tile_at(1), m, b, RULES) == 6          # only one street -> no doubling
    own(m, b.tile_at(3))
    assert rules.rent_due(b.tile_at(1), m, b, RULES) == 12         # Rule 10


@pytest.mark.parametrize("level", [1, 2, 3, 4])
def test_basin_street_monopolist_rent_is_double_competitor_per_tier(level):
    b = small_board(); t = b.tile_at(1); t.improvement_level = level
    c, m = P("competitor"), P("monopolist")
    assert rules.rent_due(t, m, b, RULES) == 2 * rules.rent_due(t, c, b, RULES)


def test_competitor_apartment_rent():
    b = small_board(); t = b.tile_at(1); t.improvement_level = 5
    assert rules.rent_due(t, P("competitor"), b, RULES) == 31


def test_mortgaged_tile_charges_nothing():
    b = small_board(); t = b.tile_at(1); t.mortgaged = True
    assert rules.rent_due(t, P("competitor"), b, RULES) == 0


def test_null_rent_raises_instead_of_inventing_numbers():
    b = small_board(); t = b.tile_at(3); t.rent_competitor = None
    with pytest.raises(MissingDataError):
        rules.rent_due(t, P("competitor"), b, RULES)


def _rails(b, owner, n):
    for i in range(n):
        t = TransportTile(index=5 + i * 10, type="transport", name=f"R{i}", price=200,
                          fare_competitor=[20] * 4, fare_monopolist=[40, 80, 160, 320])
        b.tiles[t.index] = t; own(owner, t)
    return b.tiles[5]


def test_railroad_competitor_fare_flat_regardless_of_count():
    b = small_board(); c = P("competitor"); t = _rails(b, c, 4)
    assert rules.transport_fare(t, c, b) == 20


@pytest.mark.parametrize("n,fare", [(1, 40), (2, 80), (3, 160), (4, 320)])
def test_railroad_monopolist_fare_doubles_per_company(n, fare):
    b = small_board(); m = P("monopolist"); t = _rails(b, m, n)
    assert rules.transport_fare(t, m, b) == fare


def _utils(b, owner, n):
    for i in range(n):
        t = UtilityTile(index=12 + i * 16, type="utility", name=f"U{i}", price=150,
                        dice_multiplier_competitor=[4, 4], dice_multiplier_monopolist=[4, 10])
        b.tiles[t.index] = t; own(owner, t)
    return b.tiles[12]


def test_utility_competitor_charge_flat_4x_dice():
    b = small_board(); c = P("competitor"); t = _utils(b, c, 2)
    assert rules.utility_charge(t, c, b, dice_roll=7) == 28


def test_utility_monopolist_charge_10x_when_both_owned():
    b = small_board(); m = P("monopolist"); t = _utils(b, m, 2)
    assert rules.utility_charge(t, m, b, dice_roll=7) == 70


def test_utility_monopolist_single_is_4x():
    b = small_board(); m = P("monopolist"); t = _utils(b, m, 1)
    assert rules.utility_charge(t, m, b, dice_roll=7) == 28


def test_income_tax_competitor_picks_cheaper_option():
    b = small_board()
    assert rules.income_tax_due(P("competitor", cash=1500), b, RULES) == 150   # 10% < flat
    assert rules.income_tax_due(P("competitor", cash=3000), b, RULES) == 200   # flat is cheaper
    poor = P("competitor", cash=500)
    assert rules.income_tax_due(poor, b, RULES) == 50                   # 10% of 500 < 200


def test_income_tax_monopolist_picks_cheaper_option():
    b = small_board(); m = P("monopolist", cash=500, pid=1)
    assert rules.income_tax_due(m, b, RULES) == 100                     # 20% of 500
    m.cash = 1500
    assert rules.income_tax_due(m, b, RULES) == 200                     # 300 -> capped at flat 200


def test_income_tax_counts_property_and_improvements():
    b = small_board(); c = P("competitor", cash=1000); t = b.tile_at(1); own(c, t); t.improvement_level = 2
    # 100 cash + 6 property + 10 improvements = 116
    assert rules.income_tax_due(c, b, RULES) == 116


def test_foundation_competitor_die_table():
    c = P("competitor")
    assert rules.foundation_effect(c, FakeRng([1]), RULES) == 25
    assert rules.foundation_effect(c, FakeRng([2]), RULES) == 50
    assert rules.foundation_effect(c, FakeRng([5]), RULES) == 0


def test_foundation_monopolist_pays_flat():
    assert rules.foundation_effect(P("monopolist"), FakeRng(), RULES) == -160


def test_income_tax_ignores_mortgaged_property_value():
    b = small_board(); c = P("competitor", cash=1000); t = b.tile_at(1); own(c, t); t.mortgaged = True
    assert rules.income_tax_due(c, b, RULES) == 100


def test_monopolist_with_two_of_three_is_monopolized():
    from tests.helpers import filled_board
    b = filled_board(); m = P("monopolist")
    own(m, b.tile_at(6)); assert rules.rent_due(b.tile_at(6), m, b, RULES) == 10        # 1 of 3: not monopolized
    own(m, b.tile_at(8)); assert rules.rent_due(b.tile_at(6), m, b, RULES) == 20        # 2 of 3: doubled


def test_redemption_prefers_printed_value_then_falls_back():
    assert rules.redemption_cost(basin(), RULES) == 33
    assert rules.redemption_cost(basin(mortgage_redemption=None), RULES) == 33          # 30 * 1.1
    assert rules.redemption_cost(basin(mortgage_redemption=None, mortgage_value=75), RULES) == 83
