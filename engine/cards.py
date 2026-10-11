"""Card effect handlers. effect.type is an open vocabulary: add a handler here per new type.

Each handler is (engine, player, effect_dict) -> None and goes through the engine's
money/movement helpers so every action is logged atomically (Hard Rule 4).
"""
from __future__ import annotations

from . import rules
from .errors import require


def _collect(engine, player, eff):
    src = eff.get("from", "treasurer")
    if src != "treasurer":
        raise NotImplementedError(f"collect from '{src}' - use collect_from_each_player")
    engine.treasurer.pay(player, eff["amount"])
    engine.log("card_collect", player.id, amount=eff["amount"])


def _pay(engine, player, eff):
    engine.settle(player, None, eff["amount"], "card_pay")


def _collect_from_each_player(engine, player, eff):
    for other in engine.players:
        if other is not player and not other.bankrupt and not player.bankrupt:
            engine.settle(other, player, eff["amount"], "card_collect_from_player")


def _move_to(engine, player, eff):
    engine.move_to(player, eff["tile"], collect_go=eff.get("collect_go", True))


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
    "collect": _collect,
    "pay": _pay,
    "collect_from_each_player": _collect_from_each_player,
    "move_to": _move_to,
    "move_relative": _move_relative,
    "go_to_prison": _go_to_prison,
    "get_out_free": _get_out_free,
    "pay_per_house": _pay_per_house,
}


def apply_card(engine, player, card: dict) -> None:
    effect = require(card.get("effect"), f"card {card.get('id')} effect")
    handler = HANDLERS.get(effect["type"])
    if handler is None:
        raise NotImplementedError(
            f"card {card.get('id')}: effect type '{effect['type']}' has no handler in engine/cards.py")
    handler(engine, player, effect)
