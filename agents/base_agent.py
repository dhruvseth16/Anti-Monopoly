from abc import ABC, abstractmethod
class BaseAgent(ABC):
    def __init__(self, player_id: int, params: dict):
        self.player_id = player_id
        self.params = params
    @abstractmethod
    def decide_buy(self, tile, state) -> bool: ...
    @abstractmethod
    def decide_build(self, state) -> list: ...
    @abstractmethod
    def decide_trade(self, state) -> list: ...
    def decide_pay_fine(self, state) -> bool:
        """Rule 15C.2: pay the fine voluntarily before the 1st/2nd jailed turn? Default: no."""
        return False

    @abstractmethod
    def decide_mortgage(self, state) -> list: ...
