"""Competitor / Monopolist action card decks — Rules 3, 16."""
import random
from pathlib import Path

import yaml


class Deck:
    def __init__(self, config_path: str, rng: random.Random):
        self.cards: list[dict] = yaml.safe_load(Path(config_path).read_text())
        rng.shuffle(self.cards)

    def draw(self) -> dict:
        card = self.cards.pop(0)
        self.cards.append(card)   # Rule 16 — returned to the bottom of the deck
        return card
