"""Property / transport / utility tile state — Rules 9-13, 19-20."""
from dataclasses import dataclass
from typing import Optional


@dataclass
class Tile:
    index: int
    type: str                  # start | property | transport | utility | card_draw | income_tax |
                                # property_tax | corner_prison_pricewar | corner_role_redirect | foundation
    name: Optional[str] = None
    group: Optional[str] = None
    group_size: Optional[int] = None
    price: Optional[int] = None


@dataclass
class PropertyTile(Tile):
    house_cost: Optional[int] = None
    mortgage_value: Optional[int] = None
    mortgage_redemption: Optional[int] = None
    rent_competitor: Optional[list] = None
    rent_monopolist: Optional[list] = None
    monopolist_unbuilt_rent_if_monopolized: Optional[int] = None

    owner: Optional[int] = None         # player id; None = unowned/Treasury
    improvement_level: int = 0          # 0 = no houses
    mortgaged: bool = False


@dataclass
class TransportTile(Tile):
    mortgage_value: Optional[int] = None
    mortgage_redemption: Optional[int] = None
    fare_competitor: Optional[list] = None
    fare_monopolist: Optional[list] = None
    owner: Optional[int] = None
    mortgaged: bool = False


@dataclass
class UtilityTile(Tile):
    mortgage_value: Optional[int] = None
    mortgage_redemption: Optional[int] = None
    dice_multiplier_competitor: Optional[list] = None
    dice_multiplier_monopolist: Optional[list] = None
    owner: Optional[int] = None
    mortgaged: bool = False
