"""Card effect handlers. effect.type is an open vocabulary: add a handler here per new type.

Each handler is (engine, player, effect_dict) -> None and goes through the engine's
money/movement helpers so every action is logged atomically (Hard Rule 4).

Supported types (as digitised from the physical cards):
  none                         flavour-only card, no game effect (write `effect: {type: none}`)
  collect   (from: treasurer | competitor(s) | monopolist(s))   - from a role = from EACH player of it
  pay       (to: treasurer)
  collect_from_each_monopolist / collect_from_each_player
  conditional_collect          condition: "roll N or more"  (two dice, fresh throw)
  move_to   (destination_index) forward to a tile; passing/landing on START pays $100;
            destination = the prison/price-war corner means "sent there" (Rule 15B, no START money)
  go_to_prison, get_out_free, move_relative, pay_per_house
"""
from __future__ import annotations

import re

from . import rules
from .errors import require

ROLE_ALIASES = {"competitor": "competitor", "competitors": "competitor",
                "monopolist": "monopolist", "monopolists": "monopolist"}
CONDITION = re.compile(r"^roll (\d+) or more$")


def parse_condition(text: str) -> int:
    m = CONDITION.match(str(text).strip())
    if not m:
        raise NotImplementedError(f"unsupported card condition '{text}' (supported: 'roll N or more')")
    return int(m.group(1))


def _none(engine, player, eff):
    engine.log("card_no_effect", player.id)


def _collect_from_role(engine, player, amount: int, role: str):
    for other in engine.players:
        if other is not player and other.role == role and not other.bankrupt and not player.bankrupt:
            engine.settle(other, player, amount, "card_collect_from_player")


def _collect(engine, player, eff):
    src = eff.get("from", "treasurer")
    if src == "treasurer":
        engine.treasurer.pay(player, eff["amount"])
        engine.log("card_collect", player.id, amount=eff["amount"])
    elif src in ROLE_ALIASES:
        _collect_from_role(engine, player, eff["amount"], ROLE_ALIASES[src])
    else:
        raise NotImplementedError(f"collect from '{src}' is not supported")


def _pay(engine, player, eff):
    if eff.get("to", "treasurer") != "treasurer":
        raise NotImplementedError(f"pay to '{eff['to']}' is not supported")
    engine.settle(player, None, eff["amount"], "card_pay")


def _collect_from_each_monopolist(engine, player, eff):
    _collect_from_role(engine, player, eff["amount"], "monopolist")


def _collect_from_each_player(engine, player, eff):
    for other in engine.players:
        if other is not player and not other.bankrupt and not player.bankrupt:
            engine.settle(other, player, eff["amount"], "card_collect_from_player")


def _conditional_collect(engine, player, eff):
    need = parse_condition(eff["condition"])
    total = sum(engine.roll_dice())
    engine.log("card_dice", player.id, total=total, needed=need)
    if total >= need:
        if eff.get("from", "treasurer") != "treasurer":
            raise NotImplementedError("conditional_collect only supports from: treasurer")
        engine.treasurer.pay(player, eff["amount"])
        engine.log("card_collect", player.id, amount=eff["amount"])


def destination_of(eff) -> int:
    return require(eff.get("destination_index", eff.get("tile")), "card destination_index")


def _move_to(engine, player, eff):
    idx = destination_of(eff)
    if idx == engine.prison_index():
        engine.send_to_prison(player)               # Rule 15B: sent there, no START money
    else:
        engine.move_to(player, idx, collect_go=eff.get("collect_go", True))


def _move_relative(engine, player, eff):
    engine.move_by(player, eff["steps"])


def _go_to_prison(engine, player, eff):
    engine.send_to_prison(player)


def _get_out_free(engine, player, eff):
    player.get_out_free_cards += 1
    engine.log("card_get_out_free", player.id)


def _pay_per_house(engine, player, eff):
    houses, apartments = rules.improvement_counts(player, engine.board)
    total = houses * eff["per_house"] + apartments * eff["per_apartment"]
    engine.settle(player, None, total, "card_pay_per_house")


HANDLERS = {
    "none": _none,
    "collect": _collect,
    "pay": _pay,
    "collect_from_each_monopolist": _collect_from_each_monopolist,
    "collect_from_each_player": _collect_from_each_player,
    "conditional_collect": _conditional_collect,
    "move_to": _move_to,
    "move_relative": _move_relative,
    "go_to_prison": _go_to_prison,
    "get_out_free": _get_out_free,
    "pay_per_house": _pay_per_house,
}


def apply_card(engine, player, card: dict) -> None:
    effect = require(card.get("effect"),
                     f"card {card.get('id')} effect (flavour-only cards must say `effect: {{type: none}}`)")
    handler = HANDLERS.get(effect["type"])
    if handler is None:
        raise NotImplementedError(
            f"card {card.get('id')}: effect type '{effect['type']}' has no handler in engine/cards.py")
    handler(engine, player, effect)
