"""Stage 2: treasurer bankruptcy, jail, landing, cards, agents, and full-game smoke tests."""
import random

import pytest

from agents.factory import load_agents
from agents.heuristic_agent import HeuristicAgent
from engine.errors import MissingDataError
from engine.player import Player
from engine.property import TransportTile
from engine.treasurer import Treasurer
from tests.helpers import RULES, basin, filled_board, french, make_engine, own, small_board


class Passive(HeuristicAgent):
    """Never buys/builds - isolates the rule under test."""
    def decide_buy(self, tile, state): return False
    def decide_build(self, state): return []
    def decide_mortgage(self, state): return []


def passive(pid=0):
    return Passive(pid, {"cash_floor": 0, "build_priority": "slow"})


def dice(engine, *rolls):
    q = list(rolls)
    engine.roll_dice = lambda: q.pop(0)


# ---------------- treasurer ----------------
def test_bankruptcy_resells_houses_half_price_and_transfers_assets():
    b = small_board(); debtor = Player(0, "competitor", 10); creditor = Player(1, "monopolist", 100)
    t = b.tile_at(1); own(debtor, t); t.improvement_level = 3         # 3 * 50 // 2 = 75 resale
    summary = Treasurer({}).process_bankruptcy(debtor, creditor, b)
    assert summary["houses_resold_for"] == 75
    assert debtor.bankrupt and debtor.cash == 0 and debtor.holdings == []
    assert creditor.cash == 100 + 10 + 75
    assert t.owner == 1 and t.improvement_level == 0 and 1 in creditor.holdings


def test_bankruptcy_to_treasury_returns_tiles_unowned():
    b = small_board(); debtor = Player(0, "competitor", 5); t = b.tile_at(1); own(debtor, t); t.mortgaged = True
    Treasurer({}).process_bankruptcy(debtor, None, b)
    assert t.owner is None and not t.mortgaged


# ---------------- movement / landing ----------------
def test_pass_go_pays_100():
    b = small_board(); p = Player(0, "competitor", 1500, position=38)
    e = make_engine([p], b); e._agent = passive(); e.move_by(p, 4)
    assert p.position == 2 and p.cash == 1500 + 100 + 25      # GO + card tile 2 (collect 25)


def test_rent_paid_to_owner():
    b = small_board(); a = Player(0, "competitor", 1500); o = Player(1, "competitor", 1500)
    own(o, b.tile_at(1)); e = make_engine([a, o], b); e._agent = passive(); e._last_dice = 5
    e.move_by(a, 1)
    assert a.cash == 1494 and o.cash == 1506


def test_monopolist_in_prison_collects_no_rent_but_competitor_in_pricewar_does():
    b = small_board(); a = Player(0, "competitor", 1500)
    m = Player(1, "monopolist", 1500, in_prison_or_pricewar=True); own(m, b.tile_at(1))
    e = make_engine([a, m], b); e._agent = passive(); e.move_by(a, 1)
    assert a.cash == 1500 and m.cash == 1500
    b.tile_at(1).owner = None; m.holdings.clear()
    c = Player(2, "competitor", 1500, in_prison_or_pricewar=True); own(c, b.tile_at(1))
    a.position = 0; e.players.append(c); e.move_by(a, 1)
    assert c.cash == 1506


def test_short_payer_mortgages_then_goes_bankrupt():
    b = small_board(); a = Player(0, "competitor", 3); o = Player(1, "competitor", 0)
    own(o, b.tile_at(1)); t3 = b.tile_at(3); own(a, t3)
    e = make_engine([a, o], b); e._agent = passive(); e._last_dice = 5
    b.tile_at(1).improvement_level = 5                               # rent 31
    e.move_by(a, 1)                                                  # a has 3 + mortgage 30 = 33 -> pays 31
    assert t3.mortgaged and a.cash == 2 and not a.bankrupt
    a.position = 0; b.tile_at(1).improvement_level = 5
    e.move_by(a, 1)                                                  # now cannot cover -> bankrupt
    assert a.bankrupt


# ---------------- doubles & jail ----------------
def test_doubles_give_exactly_one_extra_turn():
    b = small_board(); p = Player(0, "competitor", 1500)
    e = make_engine([p], b); dice(e, (1, 1), (2, 2), (1, 2))
    e.run_turn(p, passive())
    rolls = [ev for ev in e.events if ev["event"] == "roll"]
    assert len(rolls) == 2                                           # second doubles does NOT chain


def test_leave_jail_on_doubles_without_extra_turn():
    b = small_board(); p = Player(0, "competitor", 1500, position=10, in_prison_or_pricewar=True)
    e = make_engine([p], b); dice(e, (3, 3))
    e.run_turn(p, passive())
    assert not p.in_prison_or_pricewar and len([x for x in e.events if x["event"] == "roll"]) == 1


def test_forced_fine_on_third_failed_turn():
    b = small_board(); p = Player(0, "monopolist", 1500, position=10, in_prison_or_pricewar=True)
    e = make_engine([p], b); dice(e, (1, 2), (1, 2), (1, 2))
    e.run_turn(p, passive()); assert p.in_prison_or_pricewar and p.cash == 1500
    e.run_turn(p, passive()); assert p.in_prison_or_pricewar
    e.run_turn(p, passive())
    assert not p.in_prison_or_pricewar
    assert [x for x in e.events if x["event"] == "jail_fine"]        # fine paid BEFORE the 3rd roll


def test_get_out_free_card_used_automatically():
    b = small_board(); p = Player(0, "competitor", 1500, position=10, in_prison_or_pricewar=True,
                                  get_out_free_cards=1)
    e = make_engine([p], b); dice(e, (1, 2))
    e.run_turn(p, passive())
    assert not p.in_prison_or_pricewar and p.get_out_free_cards == 0


# ---------------- cards ----------------
def test_card_pay_per_house_and_apartment():
    b = small_board(); p = Player(0, "competitor", 1000); t = b.tile_at(1); own(p, t); t.improvement_level = 3
    cards = [{"id": "x", "effect": {"type": "pay_per_house", "per_house": 25, "per_apartment": 100}}]
    e = make_engine([p], b, comp_cards=cards); e._agent = passive()
    from engine.cards import apply_card
    apply_card(e, p, cards[0]); assert p.cash == 1000 - 75
    t.improvement_level = 5; apply_card(e, p, cards[0]); assert p.cash == 1000 - 75 - 100


def test_card_get_out_free_and_go_to_prison():
    b = small_board(); p = Player(0, "competitor", 1000); e = make_engine([p], b); e._agent = passive()
    from engine.cards import apply_card
    apply_card(e, p, {"id": "a", "effect": {"type": "get_out_free"}}); assert p.get_out_free_cards == 1
    apply_card(e, p, {"id": "b", "effect": {"type": "go_to_prison"}})
    assert p.in_prison_or_pricewar and p.position == 10


def test_unknown_card_effect_and_null_effect_fail_loudly():
    b = small_board(); p = Player(0, "competitor", 1000); e = make_engine([p], b)
    from engine.cards import apply_card
    with pytest.raises(NotImplementedError):
        apply_card(e, p, {"id": "z", "effect": {"type": "teleport"}})
    with pytest.raises(MissingDataError):
        apply_card(e, p, {"id": "n", "effect": None})


# ---------------- build rules ----------------
def test_monopolist_cannot_build_without_monopoly_competitor_can():
    b = small_board(); m = Player(0, "monopolist", 1000); c = Player(1, "competitor", 1000)
    own(m, b.tile_at(1)); e = make_engine([m, c], b)
    e._try_build(m, 1); assert b.tile_at(1).improvement_level == 0
    b.tile_at(1).owner = None; own(c, b.tile_at(1)); e._try_build(c, 1)
    assert b.tile_at(1).improvement_level == 1 and c.cash == 950
    own(m, b.tile_at(3)); b.tile_at(1).owner = m.id; m.holdings.append(1)    # now monopolist owns both
    e._try_build(m, 1); assert b.tile_at(1).improvement_level == 2


def test_build_stops_at_top_of_ladder():
    b = small_board(); m = Player(0, "monopolist", 5000)
    own(m, b.tile_at(1)); own(m, b.tile_at(3)); e = make_engine([m], b)
    for _ in range(10): e._try_build(m, 1)
    assert b.tile_at(1).improvement_level == 4                        # 3 houses + apartment for monopolist


# ---------------- agents ----------------
def test_agent_respects_cash_floor():
    b = small_board(); p = Player(0, "competitor", 500)
    from engine.engine import GameView
    v = GameView(p, [p], b, 1, RULES)
    cautious = HeuristicAgent(0, {"cash_floor": 800, "property_valuation_multiplier": {"default": 1.0},
                                  "build_priority": "slow"})
    reckless = HeuristicAgent(0, {"cash_floor": 0, "property_valuation_multiplier": {"default": 1.0},
                                  "build_priority": "immediate"})
    assert not cautious.decide_buy(b.tile_at(1), v)
    assert reckless.decide_buy(b.tile_at(1), v)


def test_agent_never_buys_null_priced_tile():
    b = small_board(); p = Player(0, "competitor", 5000)
    from engine.engine import GameView
    t = basin(price=None)
    a = HeuristicAgent(0, {"cash_floor": 0, "property_valuation_multiplier": {}, "build_priority": "slow"})
    assert not a.decide_buy(t, GameView(p, [p], b, 1, RULES))


# ---------------- full-game smoke (uses TEST-ONLY synthetic numbers via filled_board) ----------------
def build_game(seed):
    rng = random.Random(seed)
    board = filled_board()
    players = [Player(0, "competitor", 1500), Player(1, "monopolist", 1500),
               Player(2, "competitor", 1500), Player(3, "monopolist", 1500)]
    from engine.deck import Deck
    from engine.engine import Engine
    e = Engine(players, board, Deck("config/competitor_cards.yaml", rng), Deck("config/monopolist_cards.yaml", rng),
               Treasurer(RULES["bank_denominations"]), rng, RULES)
    return e, load_agents(players)


@pytest.mark.parametrize("seed", range(25))
def test_full_game_runs_with_consistent_state(seed):
    e, agents = build_game(seed)
    e.run_game(agents, max_turns=300)
    for p in e.players:
        assert p.cash >= 0
        for idx in p.holdings:
            assert e.board.tile_at(idx).owner == p.id and not p.bankrupt
        if p.bankrupt:
            assert p.holdings == [] and p.cash == 0
    for t in e.board.tiles:
        if getattr(t, "owner", None) is not None:
            assert t.index in e._player(t.owner).holdings


def test_same_seed_same_game():
    e1, a1 = build_game(7); e2, a2 = build_game(7)
    w1 = e1.run_game(a1, 200); w2 = e2.run_game(a2, 200)
    assert e1.events == e2.events and (w1 and w1.id) == (w2 and w2.id)


def test_games_actually_finish_sometimes():
    finished = 0
    for s in range(25):
        e, a = build_game(s)
        if e.run_game(a, 600) is not None: finished += 1
    assert finished > 0


def test_chaining_doubles_only_when_config_allows():
    import copy
    b = small_board(); p = Player(0, "competitor", 1500)
    e = make_engine([p], b); e.game_rules = copy.deepcopy(RULES); e.game_rules["doubles"]["extra_turn_can_chain_again"] = True
    dice(e, (1, 1), (2, 2), (1, 2))
    e.run_turn(p, passive())
    assert len([x for x in e.events if x["event"] == "roll"]) == 3


def test_rent_while_jailed_follows_config_flags():
    import copy
    b = small_board(); a = Player(0, "competitor", 1500); c = Player(1, "competitor", 1500, in_prison_or_pricewar=True)
    own(c, b.tile_at(1)); e = make_engine([a, c], b); e._agent = passive()
    e.game_rules = copy.deepcopy(RULES); e.game_rules["prison_pricewar"]["competitor_collects_rent_while_in"] = False
    e.move_by(a, 1); assert a.cash == 1500
