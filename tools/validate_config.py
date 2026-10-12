"""Checks config/*.yaml against the rulebook and reports digitisation progress.

  python -m tools.validate_config            # errors = wrong data, pending = still null (not an error)
  python -m tools.validate_config --strict   # pending items also fail the run
  python -m tools.validate_config --list     # show every pending field

Exit code 1 on any ERROR (or on pending items with --strict).
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml

from engine.cards import HANDLERS

DECK_SIZE = 25
REQUIRED_KEYS = {
    "none": [], "collect": ["amount"], "pay": ["amount"], "collect_from_each_player": ["amount"],
    "collect_from_each_monopolist": ["amount"], "conditional_collect": ["amount", "condition"],
    "move_to": ["destination_index"], "move_relative": ["steps"], "go_to_prison": [], "get_out_free": [],
    "pay_per_house": ["per_house", "per_apartment"],
}
COLLECT_FROM = {"treasurer", "competitor", "competitors", "monopolist", "monopolists"}


class _UniqueKeyLoader(yaml.SafeLoader):
    """SafeLoader that REFUSES duplicate mapping keys (plain PyYAML silently keeps the last one)."""


def _no_dupes(loader, node, deep=False):
    seen = set()
    for key_node, _ in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in seen:
            raise yaml.constructor.ConstructorError(
                None, None, f"duplicate key '{key}' (line {key_node.start_mark.line + 1}) - merge it into the "
                            "existing block instead of adding a second one", key_node.start_mark)
        seen.add(key)
    return yaml.SafeLoader.construct_mapping(loader, node, deep)


_UniqueKeyLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _no_dupes)

REQUIRED_RULE_KEYS = [
    ("pass_go_amount",), ("property_tax",), ("bank_denominations",), ("starting_cash", "total"),
    ("income_tax", "flat_amount"), ("income_tax", "competitor", "cash_percent"), ("income_tax", "monopolist", "cash_percent"),
    ("prison_pricewar", "fine"), ("prison_pricewar", "turns_before_forced_payment"),
    ("prison_pricewar", "monopolist_collects_rent_while_in"), ("prison_pricewar", "competitor_collects_rent_while_in"),
    ("doubles", "extra_turn"), ("doubles", "extra_turn_can_chain_again"),
    ("foundation", "competitor_roll", "other"), ("foundation", "monopolist_payment"),
    ("building", "competitor", "requires_monopolization"), ("building", "monopolist", "requires_monopolization"),
    ("building", "monopolist", "monopolization_min_properties"), ("building", "monopolist", "rent_doubles_once_monopolized"),
    ("mortgage", "value_fraction_of_price"), ("mortgage", "redemption_interest_rate_fallback_only"),
    ("bankruptcy", "houses_resold_to_treasury_at_half_price"),
    ("win_conditions", "active_game"), ("win_conditions", "game_a"), ("win_conditions", "game_b"),
    ("transport", "competitor_return_percent"), ("utilities", "dice_multiplier", "competitor"),
]


def check_rules(rules: dict, r: "Report"):
    for path in REQUIRED_RULE_KEYS:
        node = rules
        for k in path:
            if not isinstance(node, dict) or k not in node:
                r.err(f"game_rules.yaml: missing key {'.'.join(path)}")
                break
            node = node[k]
    mode = (rules.get("win_conditions") or {}).get("active_game")
    if mode not in ("game_a", "game_b"):
        r.err(f"game_rules.yaml: win_conditions.active_game must be game_a or game_b, got {mode!r}")


class Report:
    def __init__(self):
        self.errors, self.warnings, self.pending = [], [], []
    def err(self, m): self.errors.append(m)
    def warn(self, m): self.warnings.append(m)
    def todo(self, m): self.pending.append(m)


def check_board(board: list, rules: dict, r: Report):
    if len(board) != 40:
        r.err(f"board has {len(board)} tiles, expected 40")
    if [t["index"] for t in board] != list(range(len(board))):
        r.err("board indices must run 0..39 in order")
    groups = {}
    for t in board:
        if t["type"] == "property":
            groups.setdefault(t["group"], []).append(t)
    for g, tiles in groups.items():
        for t in tiles:
            if t["group_size"] != len(tiles):
                r.err(f"[{t['index']}] {t['name']}: group_size {t['group_size']} but {len(tiles)} tiles in '{g}'")
    frac = rules["mortgage"]["value_fraction_of_price"]
    rate = rules["mortgage"]["redemption_interest_rate_fallback_only"]
    for t in board:
        if t["type"] not in ("property", "transport", "utility"):
            continue
        tag = f"[{t['index']}] {t['name']}"
        if t.get("price") is None:
            r.todo(f"{tag}: price"); continue
        mv, red = t.get("mortgage_value"), t.get("mortgage_redemption")
        if mv is None: r.todo(f"{tag}: mortgage_value")
        elif abs(mv - t["price"] * frac) > 0.5: r.err(f"{tag}: mortgage_value {mv} != {frac} x price (Rule 12)")
        if red is None: r.todo(f"{tag}: mortgage_redemption (printed value on back of card)")
        elif mv is not None:
            if red < mv: r.err(f"{tag}: redemption {red} below mortgage value {mv}")
            elif abs(red - mv * (1 + rate)) > 1: r.warn(f"{tag}: redemption {red} is not ~{1 + rate:.0%} of {mv} - check the card")
        if t["type"] == "property":
            if t.get("house_cost") is None: r.todo(f"{tag}: house_cost")
            rc, rm = (t.get("rent") or {}).get("competitor"), (t.get("rent") or {}).get("monopolist")
            un = t.get("monopolist_unbuilt_rent_if_monopolized")
            if rc is None: r.todo(f"{tag}: rent.competitor")
            elif len(rc) != 6 or rc != sorted(rc): r.err(f"{tag}: rent.competitor needs 6 rising values, got {rc}")
            if rm is None: r.todo(f"{tag}: rent.monopolist")
            elif len(rm) != 5 or rm != sorted(rm): r.err(f"{tag}: rent.monopolist needs 5 rising values, got {rm}")
            if un is None: r.todo(f"{tag}: monopolist_unbuilt_rent_if_monopolized")
            if rc and rm and len(rc) == 6 and len(rm) == 5:
                if rc[0] != rm[0]: r.err(f"{tag}: Rule 10 - 'NO HOUSES' rent must match for both roles ({rc[0]} vs {rm[0]})")
                if any(rm[i] != 2 * rc[i] for i in range(1, 5)): r.warn(f"{tag}: monopolist rent is not 2x competitor at tiers 1-4 - check the card")
                if un is not None and un != 2 * rm[0]: r.warn(f"{tag}: unbuilt monopolised rent {un} is not 2x {rm[0]} - check the card")
        elif t["type"] == "transport":
            fc, fm = (t.get("fare") or {}).get("competitor"), (t.get("fare") or {}).get("monopolist")
            if fc is None or fm is None: r.todo(f"{tag}: fare.competitor / fare.monopolist"); continue
            want = round(t["price"] * rules["transport"]["competitor_return_percent"])
            if len(fc) != 4 or any(x != want for x in fc): r.err(f"{tag}: competitor fare must be flat ${want} x4 (Rule 19), got {fc}")
            if len(fm) != 4 or any(fm[i + 1] != 2 * fm[i] for i in range(3)): r.err(f"{tag}: monopolist fares must double per company, got {fm}")
        else:
            d = t.get("dice_multiplier") or {}
            if d.get("competitor") is None or d.get("monopolist") is None: r.todo(f"{tag}: dice_multiplier"); continue
            u = rules["utilities"]["dice_multiplier"]
            if d["competitor"] != [u["competitor"]] * 2: r.err(f"{tag}: competitor multiplier must be [{u['competitor']}, {u['competitor']}], got {d['competitor']}")
            if d["monopolist"] != [u["monopolist"]["one_owned"], u["monopolist"]["two_owned"]]: r.err(f"{tag}: monopolist multiplier must be [4, 10], got {d['monopolist']}")
    kinds = [t["type"] for t in board if t["type"] in ("property", "transport", "utility")]
    if len(kinds) != 28: r.err(f"expected 28 title cards (22 streets + 4 transport + 2 utilities), found {len(kinds)}")


def _dest_name_ok(board: list, idx: int, name) -> bool:
    t = board[idx]
    if t["type"] == "start":
        return name == "Start"
    if t["type"] == "corner_prison_pricewar":
        return name in ("Prison", "Price War")
    return name == t.get("name")


def check_deck(name: str, cards, prefix: str, r: Report, board: list | None = None):
    cards = cards or []
    if not isinstance(cards, list): r.err(f"{name}: must be a YAML list"); return
    ids = [c.get("id") for c in cards]
    if len(ids) != len(set(ids)): r.err(f"{name}: duplicate card ids")
    for c in cards:
        cid = c.get("id")
        if not str(cid).startswith(prefix): r.err(f"{name}: id '{cid}' should start with '{prefix}'")
        eff = c.get("effect")
        if eff is None:
            r.err(f"{name} {cid}: effect is null - if the card has no game effect write `effect: {{type: none}}`")
            continue
        if not isinstance(eff, dict) or "type" not in eff: r.err(f"{name} {cid}: effect.type missing"); continue
        if not c.get("text") and eff["type"] != "move_to":          # destination-only cards have no wording
            r.err(f"{name} {cid}: text is empty - copy the card wording")
        if eff["type"] not in HANDLERS: r.err(f"{name} {cid}: effect type '{eff['type']}' has no handler in engine/cards.py - tell me and I'll add one"); continue
        for k in REQUIRED_KEYS.get(eff["type"], []):
            if eff.get(k) is None: r.err(f"{name} {cid}: effect '{eff['type']}' needs '{k}'")
        if eff["type"] in ("collect", "conditional_collect") and eff.get("from", "treasurer") not in COLLECT_FROM:
            r.err(f"{name} {cid}: unsupported 'from: {eff.get('from')}'")
        if eff["type"] == "pay" and eff.get("to", "treasurer") != "treasurer":
            r.err(f"{name} {cid}: pay 'to: {eff.get('to')}' is not supported (only treasurer)")
        if eff["type"] == "conditional_collect" and eff.get("condition") and not re.match(r"^roll \d+ or more$", str(eff["condition"])):
            r.err(f"{name} {cid}: condition must look like 'roll 8 or more'")
        if eff["type"] == "move_to":
            idx = eff.get("destination_index")
            if not isinstance(idx, int) or not 0 <= idx <= 39:
                r.err(f"{name} {cid}: destination_index must be a tile index 0-39")
            elif board is not None and not _dest_name_ok(board, idx, eff.get("destination")):
                r.err(f"{name} {cid}: destination '{eff.get('destination')}' does not match board tile {idx} ('{board[idx].get('name') or board[idx]['type']}')")
    if len(cards) < DECK_SIZE: r.todo(f"{name}: {len(cards)}/{DECK_SIZE} cards digitised")
    elif len(cards) > DECK_SIZE: r.err(f"{name}: {len(cards)} cards, the box has {DECK_SIZE}")


def load_yaml(config_dir: str, name: str):
    return yaml.load(Path(config_dir, name).read_text(), Loader=_UniqueKeyLoader)


def run_checks(config_dir: str = "config") -> Report:
    """All checks as a Report. Raises yaml.YAMLError on unreadable files (incl. duplicate keys)."""
    r = Report()
    rules = load_yaml(config_dir, "game_rules.yaml")
    check_rules(rules, r)
    if r.errors:                                   # cannot cross-check the board against broken rules
        return r
    check_board(load_yaml(config_dir, "board.yaml"), rules, r)
    board = load_yaml(config_dir, "board.yaml")
    check_deck("competitor_cards.yaml", load_yaml(config_dir, "competitor_cards.yaml"), "comp_", r, board)
    check_deck("monopolist_cards.yaml", load_yaml(config_dir, "monopolist_cards.yaml"), "mono_", r, board)
    return r


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config-dir", default="config")
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args(argv)
    try:
        r = run_checks(a.config_dir)
    except yaml.YAMLError as exc:
        print(f"ERROR {exc}")
        sys.exit(1)
    for label, items in (("ERROR", r.errors), ("WARN ", r.warnings)):
        for m in items: print(f"{label} {m}")
    if a.list:
        for m in r.pending: print(f"TODO  {m}")
    print(f"\n{len(r.errors)} errors, {len(r.warnings)} warnings, {len(r.pending)} pending fields"
          + ("" if a.list else "  (use --list to see them)"))
    sys.exit(1 if r.errors or (a.strict and r.pending) else 0)


if __name__ == "__main__":
    main()
