"""OPT-IN synthetic numbers for plumbing checks before digitisation is finished.

NEVER used by the engine and never written to config/. Results from a filled board say NOTHING about
real game balance - they only prove the loop runs end to end.
"""
from engine.property import PropertyTile, TransportTile, UtilityTile

BANNER = "*** SYNTHETIC PLACEHOLDER DATA in null fields - NOT valid for balance conclusions ***"


def fill_placeholders(board):
    for t in board.tiles:
        if isinstance(t, PropertyTile):
            base = max(2, t.price // 10)
            t.house_cost = t.house_cost or 50 * (t.price // 100 + 1)
            t.mortgage_redemption = t.mortgage_redemption or round(t.mortgage_value * 1.1)
            if t.rent_competitor is None:
                t.rent_competitor = [base, base * 3, base * 5, base * 8, base * 10, base * 12]
                t.rent_monopolist = [base] + [2 * r for r in t.rent_competitor[1:5]]
                t.monopolist_unbuilt_rent_if_monopolized = 2 * base
        elif isinstance(t, TransportTile) and t.fare_competitor is None:
            t.fare_competitor, t.fare_monopolist = [20] * 4, [40, 80, 160, 320]
            t.mortgage_redemption = t.mortgage_redemption or 110
        elif isinstance(t, UtilityTile) and t.dice_multiplier_competitor is None:
            t.dice_multiplier_competitor, t.dice_multiplier_monopolist = [4, 4], [4, 10]
            t.mortgage_redemption = t.mortgage_redemption or 83
    return board
