"""Loads config/board.yaml into Tile objects and exposes board-wide queries."""
from pathlib import Path

import yaml

from .property import PropertyTile, Tile, TransportTile, UtilityTile

TILE_CLASSES = {
    "property": PropertyTile,
    "transport": TransportTile,
    "utility": UtilityTile,
}

# nested YAML keys that need flattening into the dataclasses' flat field names
_NESTED_FIELD_MAP = {
    "rent": {"competitor": "rent_competitor", "monopolist": "rent_monopolist"},
    "fare": {"competitor": "fare_competitor", "monopolist": "fare_monopolist"},
    "dice_multiplier": {
        "competitor": "dice_multiplier_competitor",
        "monopolist": "dice_multiplier_monopolist",
    },
}


class Board:
    def __init__(self, config_path: str = "config/board.yaml"):
        self.tiles: list[Tile] = []
        self._load(config_path)

    def _load(self, config_path: str) -> None:
        raw = yaml.safe_load(Path(config_path).read_text())
        for entry in raw:
            cls = TILE_CLASSES.get(entry["type"], Tile)
            kwargs = dict(entry)
            for nested_key, flat_map in _NESTED_FIELD_MAP.items():
                nested = kwargs.pop(nested_key, None)
                if nested:
                    for src, dst in flat_map.items():
                        kwargs[dst] = nested.get(src)
            filtered = {k: v for k, v in kwargs.items() if k in cls.__dataclass_fields__}
            self.tiles.append(cls(**filtered))

    def tile_at(self, index: int) -> Tile:
        return self.tiles[index % len(self.tiles)]

    def properties_in_group(self, group: str) -> list[PropertyTile]:
        return [t for t in self.tiles if isinstance(t, PropertyTile) and t.group == group]

    def owned_count_in_group(self, group: str, player_id: int) -> int:
        return sum(1 for t in self.properties_in_group(group) if t.owner == player_id)
