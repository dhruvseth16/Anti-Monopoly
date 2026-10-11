"""Agent interface every 'mind' implements. Stage 2 fills in concrete decision logic."""
from abc import ABC, abstractmethod


class BaseAgent(ABC):
    def __init__(self, player_id: int, params: dict):
        self.player_id = player_id
        self.params = params

    @abstractmethod
    def decide_buy(self, tile, state) -> bool: ...

    @abstractmethod
    def decide_build(self, state) -> list:
        """Return [(tile_index, action), ...] to perform this turn, e.g. [(1, 'build')]."""

    @abstractmethod
    def decide_trade(self, state) -> list:
        """Return proposed trades this turn, or []."""

    @abstractmethod
    def decide_mortgage(self, state) -> list:
        """Return tile indices to mortgage/unmortgage this turn, or []."""
