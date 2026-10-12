"""Every card in the shipped decks must run, and each effect type behaves as the rulebook says."""
import copy
from pathlib import Path

import pytest
import yaml

from engine.cards import apply_card, parse_condition
from engine.player import Player
from tests.helpers import RULES, FakeRng, filled_board, make_engine, own
from tests.test_engine import dice, passive

DECKS = {"competitor": yaml.safe_load(Path("config/competitor_cards.yaml").read_text()),
         "monopolist": yaml.safe_load(Path("config/monopolist_cards.yaml").read_text())}


def setup(role="competitor", n_other=0, cash=1000, position=7):
    board = filled_board()
    me = Player(0, role, cash, position=position)
    others = [Player(i + 1, "monopolist" if role == "competitor" else "competitor", 1000) for i in range(n_other)]
    e = make_engine([me, *others], board); e._agent = passive()
    return e, me, others


def card(**eff): return {"id": "x", "text": "t", "effect": eff}


def test_deck_sizes_and_unique_ids():
    for name, deck in DECKS.items():
        assert len(deck) == 25 and len({c["id"] for c in deck}) == 25


@pytest.mark.parametrize("role", ["competitor", "monopolist"])
def test_every_shipped_card_applies_without_error(role):
    for c in DECKS[role]:
        e, me, others = setup(role, n_other=2, position=20)
        dice(e, *[(3, 4)] * 20)
        apply_card(e, me, c)                      # must not raise
        assert me.cash >= 0 or me.bankrupt


def test_none_card_is_a_logged_noop():
    e, me, _ = setup(); apply_card(e, me, card(type="none"))
    assert me.cash == 1000 and e.events[-1]["event"] == "card_no_effect"


def test_null_effect_is_rejected_not_silently_ignored():
    from engine.errors import MissingDataError
    e, me, _ = setup()
    with pytest.raises(MissingDataError): apply_card(e, me, {"id": "x", "text": "t", "effect": None})


def test_move_to_start_pays_go_money_and_wraps_forward():
    e, me, _ = setup(position=20); apply_card(e, me, card(type="move_to", destination="Start", destination_index=0))
    assert me.position == 0 and me.cash == 1100


def test_move_to_property_passing_start_collects_and_lands_unowned_no_buy():
    e, me, _ = setup(position=30); apply_card(e, me, card(type="move_to", destination_index=12))
    assert me.position == 12 and me.cash == 1100                       # passed START, declined the utility


def test_move_to_property_without_passing_start_pays_no_go():
    e, me, _ = setup(position=7); apply_card(e, me, card(type="move_to", destination_index=12))
    assert me.cash == 1000


def test_move_to_owned_tile_pays_rent():
    e, me, others = setup(role="competitor", n_other=1, position=7)
    own(others[0], e.board.tile_at(29))
    apply_card(e, me, card(type="move_to", destination_index=29))
    assert me.cash == 1000 - 28 and others[0].cash == 1028             # competitor-owned? other is monopolist: 0 houses same rent


def test_move_to_utility_owned_uses_fresh_throw():
    e, me, others = setup(n_other=1, position=7); own(others[0], e.board.tile_at(12)); dice(e, (3, 4))
    apply_card(e, me, card(type="move_to", destination_index=12))
    assert me.cash == 1000 - 4 * 7                                      # monopolist owns ONE utility -> 4x


def test_move_to_price_war_means_sent_there_without_start_money():
    e, me, _ = setup(position=30); apply_card(e, me, card(type="move_to", destination="Price War", destination_index=10))
    assert me.in_prison_or_pricewar and me.position == 10 and me.cash == 1000


def test_go_to_prison_card():
    e, me, _ = setup("monopolist", position=30)
    apply_card(e, me, card(type="go_to_prison", destination="Prison", destination_index=10, miss_turns_collecting_rent=2))
    assert me.in_prison_or_pricewar and me.position == 10 and me.cash == 1000


@pytest.mark.parametrize("roll,paid", [((3, 4), False), ((4, 4), True), ((6, 6), True)])
def test_conditional_collect_roll_8_or_more(roll, paid):
    e, me, _ = setup("monopolist"); dice(e, roll)
    apply_card(e, me, card(type="conditional_collect", condition="roll 8 or more", amount=75, **{"from": "treasurer"}))
    assert me.cash == (1075 if paid else 1000)


def test_conditional_collect_roll_10_or_more_boundary():
    for total, paid in ((9, False), (10, True)):
        e, me, _ = setup(); dice(e, (total - 4, 4))
        apply_card(e, me, card(type="conditional_collect", condition="roll 10 or more", amount=75, **{"from": "treasurer"}))
        assert me.cash == (1075 if paid else 1000)


def test_bad_condition_text_fails_loudly():
    with pytest.raises(NotImplementedError): parse_condition("roll doubles")


def test_competitor_collects_25_from_each_monopolist_only():
    e, me, others = setup("competitor", n_other=2)
    bystander = Player(9, "competitor", 1000); e.players.append(bystander)
    apply_card(e, me, card(type="collect_from_each_monopolist", amount=25, **{"from": "monopolists"}))
    assert me.cash == 1050 and [o.cash for o in others] == [975, 975] and bystander.cash == 1000


def test_monopolist_collects_25_from_each_competitor():
    e, me, others = setup("monopolist", n_other=2)
    apply_card(e, me, card(type="collect", amount=25, **{"from": "competitor"}))
    assert me.cash == 1050 and [o.cash for o in others] == [975, 975]


def test_collect_from_broke_player_forces_liquidation_then_bankruptcy_to_the_collector():
    e, me, others = setup("competitor", n_other=1); others[0].cash = 0
    apply_card(e, me, card(type="collect_from_each_monopolist", amount=25, **{"from": "monopolists"}))
    assert others[0].bankrupt and me.cash == 1000


def test_pay_to_treasurer_and_collect_from_treasurer():
    e, me, _ = setup(); apply_card(e, me, card(type="pay", amount=75, to="treasurer"))
    apply_card(e, me, card(type="collect", amount=25, **{"from": "treasurer"}))
    assert me.cash == 950


def test_unsupported_pay_target_fails_loudly():
    e, me, _ = setup()
    with pytest.raises(NotImplementedError): apply_card(e, me, card(type="pay", amount=5, to="competitor"))
