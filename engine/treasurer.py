"""Treasury / banking operations — Rules 2, 12, 13, 24, 26."""
from __future__ import annotations

from .player import Player


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

    def process_bankruptcy(self, bankrupt: Player, creditor: Player | None) -> None:
        """Rule 24 — creditor is None when the Treasury itself bankrupted the player."""
        raise NotImplementedError  # stage 2: house resale at half price, asset transfer
