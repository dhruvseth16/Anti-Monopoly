"""Player state — Rules 5, 6, 8, 15."""
from dataclasses import dataclass, field


@dataclass
class Player:
    id: int
    role: str                 # "competitor" | "monopolist"
    cash: int
    position: int = 0
    in_prison_or_pricewar: bool = False
    turns_in_prison_or_pricewar: int = 0
    holdings: list = field(default_factory=list)   # tile indices owned
    bankrupt: bool = False

    @property
    def pawn_color(self) -> str:
        return "green" if self.role == "competitor" else "blue"   # Rule 6
