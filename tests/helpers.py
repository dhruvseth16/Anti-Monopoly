"""Test-only helpers. Synthetic numbers live HERE, never in config/ (Hard Rule 5)."""
import random
from pathlib import Path

import yaml

from engine.board import Board
from engine.engine import Engine
from engine.player import Player
from engine.property import PropertyTile, TransportTile, UtilityTile
from engine.treasurer import Treasurer

RULES = yaml.safe_load(Path("config/game_rules.yaml").read_text())   # tests use the REAL rules file


class FakeDeck:
    def __init__(self, cards): self.cards = list(cards)
    def draw(self):
        c = self.cards.pop(0); self.cards.append(c); return c


class FakeRng:
    """randint returns queued values; falls back to 1."""
    def __init__(self, values=()): self.values = list(values)
    def randint(self, a, b): return self.values.pop(0) if self.values else a
    def shuffle(self, x): pass


def basin(**kw):
    d = dict(index=1, type="property", name="New Orleans: Basin Street", group="new_orleans", group_size=2,
             price=60, house_cost=50, mortgage_value=30, mortgage_redemption=33,
             rent_competitor=[6, 11, 16, 21, 26, 31], rent_monopolist=[6, 22, 32, 42, 52],
             monopolist_unbuilt_rent_if_monopolized=12)
    d.update(kw); return PropertyTile(**d)


def french(**kw):
    d = dict(index=3, type="property", name="New Orleans: French Quarter", group="new_orleans", group_size=2,
             price=60, house_cost=50, mortgage_value=30, mortgage_redemption=33,
             rent_competitor=[6, 11, 16, 21, 26, 31], rent_monopolist=[6, 22, 32, 42, 52],
             monopolist_unbuilt_rent_if_monopolized=12)
    d.update(kw); return PropertyTile(**d)


def small_board(extra=()):
    """40 slots so modulo maths matches the real board; only a few tiles matter."""
    from engine.property import Tile
    b = Board.__new__(Board)
    b.tiles = [Tile(index=i, type="start" if i == 0 else "card_draw") for i in range(40)]
    b.tiles[10] = Tile(index=10, type="corner_prison_pricewar")
    for t in (basin(), french(), *extra):
        b.tiles[t.index] = t
    return b


def filled_board(path="config/board.yaml"):
    """Real board.yaml with TEST-ONLY synthetic numbers where config is still null."""
    b = Board(path)
    for t in b.tiles:
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
    return b


def make_engine(players, board, seed=1, rng=None, comp_cards=None, mono_cards=None):
    comp = FakeDeck(comp_cards or [{"id": "c", "effect": {"type": "collect", "amount": 25, "from": "treasurer"}}])
    mono = FakeDeck(mono_cards or [{"id": "m", "effect": {"type": "collect", "amount": 75, "from": "treasurer"}}])
    return Engine(players, board, comp, mono, Treasurer(RULES["bank_denominations"]), rng or random.Random(seed), RULES)


def own(player, tile):
    tile.owner = player.id
    player.holdings.append(tile.index)
