"""
Skeleton for stage 2. Each test encodes an exact expected number from the rulebook
or a digitized card, so engine/rules.py has a correctness target before it's written.
All xfail (NotImplementedError) until the real logic lands.
"""
import pytest

from engine.rules import income_tax_due, rent_due, transport_fare, utility_charge  # noqa: F401


@pytest.mark.xfail(raises=NotImplementedError, strict=True)
def test_basin_street_competitor_rent_no_houses():
    # New Orleans: Basin Street, Competitor, 0 houses -> $6 (Rule 9, board.yaml)
    rent_due(None, None)


@pytest.mark.xfail(raises=NotImplementedError, strict=True)
def test_basin_street_monopolist_rent_doubles_once_monopolized():
    # Monopolist owning both New Orleans streets, 0 houses -> $12, not $6 (Rule 10)
    rent_due(None, None)


@pytest.mark.xfail(raises=NotImplementedError, strict=True)
def test_basin_street_monopolist_rent_is_double_competitor_per_tier():
    # 1 house: competitor $11 -> monopolist $22; 2 houses: $16 -> $32; etc. (Rule 10)
    rent_due(None, None)


@pytest.mark.xfail(raises=NotImplementedError, strict=True)
def test_railroad_competitor_fare_flat_regardless_of_count():
    # Competitor owns all 4 railroads -> still $20 each (Rule 19)
    transport_fare(None, None, None)


@pytest.mark.xfail(raises=NotImplementedError, strict=True)
def test_railroad_monopolist_fare_doubles_per_company():
    # Monopolist: 1 owned $40, 2 owned $80, 3 owned $160, 4 owned $320 (Rule 19)
    transport_fare(None, None, None)


@pytest.mark.xfail(raises=NotImplementedError, strict=True)
def test_utility_competitor_charge_flat_4x_dice():
    # Competitor owns both utilities -> still 4x dice, not 10x (Rule 20)
    utility_charge(None, None, None, dice_roll=7)


@pytest.mark.xfail(raises=NotImplementedError, strict=True)
def test_utility_monopolist_charge_10x_when_both_owned():
    # Monopolist owning both utilities -> 10x dice roll (Rule 20)
    utility_charge(None, None, None, dice_roll=7)


@pytest.mark.xfail(raises=NotImplementedError, strict=True)
def test_income_tax_competitor_picks_cheaper_option():
    # Rule 17: competitor pays min($200, 10% cash + 10% property + 10% improvements)
    income_tax_due(None, None, None)


@pytest.mark.xfail(raises=NotImplementedError, strict=True)
def test_income_tax_monopolist_picks_cheaper_option():
    # Rule 17: monopolist pays min($200, 20% cash + 10% property + 10% improvements)
    income_tax_due(None, None, None)
