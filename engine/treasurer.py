"""Treasury / banking operations — Rules 2, 12, 13, 24, 26."""
from __future__ import annotations

from .errors import require
# pyrefly: ignore [missing-import]
from .engine.player import Player
from .property import PropertyTile


class Treasurer:
    def __init__(self, bank_denominations: dict):
        self.bank_denominations = dict(bank_denominations)   # bill-level tracking not yet used

    def pay(self, player: Player, amount: int) -> None:
        player.cash += amount

    def collect(self, player: Player, amount: int) -> bool:
        """Returns False if the player can't cover amount — caller handles asset sale/bankruptcy."""
        if player.cash < amount:
            return False
        player.cash -= amount
        return True

    def transfer(self, payer: Player, payee: Player, amount: int) -> bool:
        if payer.cash < amount:
            return False
        payer.cash -= amount
        payee.cash += amount
        return True

    def process_bankruptcy(self, bankrupt: Player, creditor: Player | None, board, resell_houses: bool = True) -> dict:
        """Rule 24 — creditor is None when the Treasury itself bankrupted the player.

        1. Houses/apartments are resold to the Treasury at half build cost (cash goes to the bankrupt).
        2. All remaining cash and every holding passes to the creditor (or back to the Treasury).
        """
        resale = 0
        for idx in bankrupt.holdings:
            t = board.tile_at(idx)
            if resell_houses and isinstance(t, PropertyTile) and t.improvement_level > 0:
                resale += (require(t.house_cost, f"{t.name} house_cost") * t.improvement_level) // 2
                t.improvement_level = 0
        bankrupt.cash += resale

        cash_moved = bankrupt.cash
        bankrupt.cash = 0
        if creditor is not None:
            creditor.cash += cash_moved

        moved = list(bankrupt.holdings)
        for idx in moved:
            t = board.tile_at(idx)
            if creditor is not None:
                t.owner = creditor.id               # mortgaged state travels with the tile
                creditor.holdings.append(idx)
            else:
                t.owner = None
                t.mortgaged = False
        bankrupt.holdings.clear()
        bankrupt.bankrupt = True
        return {"houses_resold_for": resale, "cash_transferred": cash_moved, "tiles": moved}
