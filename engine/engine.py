"""Turn loop, dice, movement, win-condition checks — Rules 1, 7, 8."""
from __future__ import annotations

import random

from .board import Board
from .deck import Deck
from .player import Player
from .treasurer import Treasurer


class Engine:
    def __init__(
        self,
        players: list[Player],
        board: Board,
        competitor_deck: Deck,
        monopolist_deck: Deck,
        treasurer: Treasurer,
        rng: random.Random,
        game_rules: dict,
    ):
        self.players = players
        self.board = board
        self.competitor_deck = competitor_deck
        self.monopolist_deck = monopolist_deck
        self.treasurer = treasurer
        self.rng = rng
        self.game_rules = game_rules
        self.turn_count = 0

    def roll_dice(self) -> tuple[int, int]:
        return self.rng.randint(1, 6), self.rng.randint(1, 6)

    def run_turn(self, player: Player, agent) -> None:
        raise NotImplementedError  # stage 2+: movement, landing resolution, agent decisions

    def check_winner(self) -> Player | None:
        raise NotImplementedError  # stage 2+: Game A / Game B per Rule 1

    def run_game(self, max_turns: int = 1000) -> Player | None:
        raise NotImplementedError  # stage 2+: full loop
