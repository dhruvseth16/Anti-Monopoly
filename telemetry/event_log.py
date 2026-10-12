"""Atomic event schema (Hard Rule 4). The engine appends plain dicts; this turns them into a flat table.

Columns: game_id, seq, turn, event_type, player_id, tile, amount, payload
`tile` and `amount` are lifted out because most analysis filters on them; everything else rides in
`payload` as a JSON string so new event fields never break the schema.
"""
from __future__ import annotations

import json

import pandas as pd

COLUMNS = ["game_id", "seq", "turn", "event_type", "player_id", "tile", "amount", "payload"]
INT_COLUMNS = ["seq", "turn", "player_id", "tile", "amount"]


def events_to_frame(events: list[dict], game_id: str) -> pd.DataFrame:
    rows = []
    for seq, ev in enumerate(events):
        rest = dict(ev)
        rows.append({
            "game_id": game_id,
            "seq": seq,
            "turn": rest.pop("turn"),
            "event_type": rest.pop("event"),
            "player_id": rest.pop("player_id"),
            "tile": rest.pop("tile", None),
            "amount": rest.pop("amount", None),
            "payload": json.dumps(rest, sort_keys=True, default=str),
        })
    df = pd.DataFrame(rows, columns=COLUMNS)
    for col in INT_COLUMNS:
        df[col] = df[col].astype("Int64")        # nullable ints: not every event has a player/tile/amount
    return df
