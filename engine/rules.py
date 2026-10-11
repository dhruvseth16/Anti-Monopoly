"""Role-specific math: rent, income tax, utility/transport fares, foundation — Rules 9-21.

Pure functions: they read state and return numbers; they never mutate anything.
Every config value comes from tile fields or the game_rules dict (Hard Rule 1);
a null field raises MissingDataError (Hard Rule 5).
"""
from __future__ import annotations

import math

from .errors import require
from .player import Player
from .property import PropertyTile, TransportTile, UtilityTile


# ---------- helpers -------------------------------------------------------
def _role_list(tile, role: str, comp_attr: str, mono_attr: str, label: str) -> list:
    attr = comp_attr if role == "competitor" else mono_attr
    return require(getattr(tile, attr), f"{tile.name} {label}.{role}")


def max_improvement_level(tile: PropertyTile, role: str) -> int:
    """Top rung of the rent ladder for this role (competitor 5, monopolist 4 once digitised)."""
    return len(_role_list(tile, role, "rent_competitor", "rent_monopolist", "rent")) - 1


def has_monopoly(tile: PropertyTile, owner: Player, board, rules_config: dict) -> bool:
    """Monopolisation = owning at least `monopolization_min_properties` of the group (capped at group size)."""
    need = rules_config["building"]["monopolist"]["monopolization_min_properties"]
    size = require(tile.group_size, f"{tile.name} group_size")
    return board.owned_count_in_group(tile.group, owner.id) >= min(need, size)


def redemption_cost(tile, rules_config: dict) -> int:
    """Printed redemption value if digitised; otherwise the config fallback (mortgage value + interest)."""
    if tile.mortgage_redemption is not None:
        return tile.mortgage_redemption
    mortgage = require(tile.mortgage_value, f"{tile.name} mortgage_value")
    rate = rules_config["mortgage"]["redemption_interest_rate_fallback_only"]
    return math.floor(mortgage * (1 + rate) + 0.5)


def _owned_count(board, cls, owner: Player) -> int:
    return sum(1 for t in board.tiles if isinstance(t, cls) and t.owner == owner.id)


def improvement_counts(player: Player, board) -> tuple[int, int]:
    """(houses, apartments) across the player's holdings. Top rung = apartment."""
    houses = apartments = 0
    for idx in player.holdings:
        t = board.tile_at(idx)
        if isinstance(t, PropertyTile) and t.improvement_level > 0:
            if t.improvement_level >= max_improvement_level(t, player.role):
                apartments += 1
            else:
                houses += t.improvement_level
    return houses, apartments


def net_worth(player: Player, board) -> int:
    """Cash + property at price (mortgaged: at mortgage value) + improvements at build cost."""
    total = player.cash
    for idx in player.holdings:
        t = board.tile_at(idx)
        price = require(t.price, f"{t.name} price")
        total += require(t.mortgage_value, f"{t.name} mortgage_value") if t.mortgaged else price
        if isinstance(t, PropertyTile) and t.improvement_level:
            total += require(t.house_cost, f"{t.name} house_cost") * t.improvement_level
    return total


# ---------- rent (Rules 9, 10, 11) ---------------------------------------
def rent_due(tile: PropertyTile, owner: Player, board, rules_config: dict) -> int:
    if tile.mortgaged:
        return 0
    rents = _role_list(tile, owner.role, "rent_competitor", "rent_monopolist", "rent")
    level = tile.improvement_level
    if level >= len(rents):
        raise ValueError(f"{tile.name}: improvement level {level} exceeds the {owner.role} rent ladder")
    # Rule 10: a monopolist who controls the whole colour group charges doubled rent on unbuilt tiles
    if (owner.role == "monopolist" and level == 0
            and rules_config["building"]["monopolist"]["rent_doubles_once_monopolized"]
            and has_monopoly(tile, owner, board, rules_config)):
        return require(tile.monopolist_unbuilt_rent_if_monopolized,
                       f"{tile.name} monopolist_unbuilt_rent_if_monopolized")
    return rents[level]


# ---------- transport (Rule 19) ------------------------------------------
def transport_fare(tile: TransportTile, owner: Player, board) -> int:
    if tile.mortgaged:
        return 0
    fares = _role_list(tile, owner.role, "fare_competitor", "fare_monopolist", "fare")
    count = max(1, _owned_count(board, TransportTile, owner))
    return fares[min(count, len(fares)) - 1]


# ---------- utility (Rule 20) --------------------------------------------
def utility_charge(tile: UtilityTile, owner: Player, board, dice_roll: int) -> int:
    if tile.mortgaged:
        return 0
    mults = _role_list(tile, owner.role, "dice_multiplier_competitor", "dice_multiplier_monopolist",
                       "dice_multiplier")
    count = max(1, _owned_count(board, UtilityTile, owner))
    return mults[min(count, len(mults)) - 1] * dice_roll


# ---------- income tax (Rule 17) -----------------------------------------
def income_tax_due(player: Player, board, rules_config: dict) -> int:
    """min(flat, role-specific % of cash + property + improvements). Rounded half-up."""
    cfg = rules_config["income_tax"]
    pct = cfg[player.role]
    prop_value = improvements = 0
    for idx in player.holdings:
        t = board.tile_at(idx)
        if not t.mortgaged:                       # property % applies to UNMORTGAGED listed prices only
            prop_value += require(t.price, f"{t.name} price")
        if isinstance(t, PropertyTile) and t.improvement_level:
            improvements += require(t.house_cost, f"{t.name} house_cost") * t.improvement_level
    formula = (player.cash * pct["cash_percent"] + prop_value * pct["property_percent"]
               + improvements * pct["improvement_percent"])
    return min(cfg["flat_amount"], math.floor(formula + 0.5))


# ---------- foundation (Rule 21) -----------------------------------------
def foundation_effect(player: Player, rng, rules_config: dict) -> int:
    """Signed cash effect: positive = player receives, negative = player pays."""
    cfg = rules_config["foundation"]
    if player.role == "competitor":
        table = cfg["competitor_roll"]
        die = rng.randint(1, 6)
        return table.get(str(die), table["other"])
    return -cfg["monopolist_payment"]
