"""Turn loop, dice, movement, landing resolution, win conditions — Rules 1, 7, 8, 14, 15, 24."""
from __future__ import annotations

import random
from dataclasses import dataclass

from . import rules
from .board import Board
from .cards import apply_card
from .deck import Deck
from .errors import require
from .player import Player
from .property import PropertyTile, TransportTile, UtilityTile
from .treasurer import Treasurer

OWNABLE = (PropertyTile, TransportTile, UtilityTile)


@dataclass
class GameView:
    """Read-only snapshot handed to agents. Agents must not mutate engine state."""
    player: Player
    players: list
    board: Board
    turn: int
    rules: dict


class Engine:
    def __init__(
        self,
        players: list[Player],
        board: Board,
        competitor_deck: Deck,
        monopolist_deck: Deck,
        treasurer: Treasurer,
        rng: random.Random,
        game_rules: dict,
    ):
        self.players = players
        self.board = board
        self.competitor_deck = competitor_deck
        self.monopolist_deck = monopolist_deck
        self.treasurer = treasurer
        self.rng = rng
        self.game_rules = game_rules
        self.turn_count = 0
        self.events: list[dict] = []     # atomic event log (Hard Rule 4); stage 3 moves this to telemetry/
        self._agent = None

    # ------------------------------------------------------------ basics
    def log(self, event: str, player_id, **payload) -> None:
        self.events.append({"turn": self.turn_count, "event": event, "player_id": player_id, **payload})

    def roll_dice(self) -> tuple[int, int]:
        return self.rng.randint(1, 6), self.rng.randint(1, 6)

    def _player(self, player_id: int) -> Player:
        return next(p for p in self.players if p.id == player_id)

    def _view(self, player: Player) -> GameView:
        return GameView(player, self.players, self.board, self.turn_count, self.game_rules)

    # ------------------------------------------------------------ turn
    def run_turn(self, player: Player, agent) -> None:
        if player.bankrupt:
            return
        self._agent = agent
        self._play_roll(player, agent, allow_extra=True)

    def _play_roll(self, player: Player, agent, allow_extra: bool) -> None:
        # Rule 15: card / fine is settled BEFORE the roll, then the turn is played normally.
        if player.in_prison_or_pricewar and not self._pre_roll_jail(player):
            return                                      # went bankrupt paying the fine
        d1, d2 = self.roll_dice()
        doubles = d1 == d2
        self.log("roll", player.id, dice=[d1, d2])

        if player.in_prison_or_pricewar:
            if doubles:
                self._release(player, "doubles")        # Rule 15C.1; Rule 15D: counts as ordinary doubles
            else:
                player.turns_in_prison_or_pricewar += 1
                self._post_move(player, agent)
                return

        self.move_by(player, d1 + d2)
        if player.bankrupt:
            return
        self._post_move(player, agent)

        # Rule 7: doubles -> one extra turn; chaining only if config says so.
        cfg = self.game_rules["doubles"]
        if doubles and allow_extra and cfg["extra_turn"] and not player.in_prison_or_pricewar:
            self._play_roll(player, agent, allow_extra=cfg["extra_turn_can_chain_again"])

    def _post_move(self, player: Player, agent) -> None:
        if player.bankrupt:
            return
        view = self._view(player)
        for idx, action in agent.decide_build(view):
            if action == "build":
                self._try_build(player, idx)
        for idx in agent.decide_mortgage(view):
            self._try_mortgage_toggle(player, idx)
        # decide_trade is intentionally NOT called in stage 2 (stubbed until stage 3)

    # ------------------------------------------------------------ movement
    def move_by(self, player: Player, steps: int) -> None:
        n = len(self.board.tiles)
        old = player.position
        player.position = (old + steps) % n
        if steps > 0 and old + steps >= n:
            self._pass_go(player)
        self.log("move", player.id, to=player.position)
        self._land(player)

    def move_to(self, player: Player, target: int, collect_go: bool = True) -> None:
        n = len(self.board.tiles)
        old = player.position
        player.position = target % n
        if collect_go and player.position < old:
            self._pass_go(player)
        self.log("move", player.id, to=player.position)
        self._land(player)

    def _pass_go(self, player: Player) -> None:
        amount = self.game_rules["pass_go_amount"]
        self.treasurer.pay(player, amount)
        self.log("pass_go", player.id, amount=amount)

    def prison_index(self) -> int:
        return next(t.index for t in self.board.tiles if t.type == "corner_prison_pricewar")

    def send_to_prison(self, player: Player) -> None:
        player.position = self.prison_index()
        player.in_prison_or_pricewar = True
        player.turns_in_prison_or_pricewar = 0
        self.log("go_to_prison", player.id)

    def _pre_roll_jail(self, player: Player) -> bool:
        """Get-out-free card; forced fine after the free-roll turns; or a voluntary fine (Rule 15C.2).
        Returns False only if the player went bankrupt."""
        cfg = self.game_rules["prison_pricewar"]
        if player.get_out_free_cards > 0:
            player.get_out_free_cards -= 1
            self._release(player, "card")
        elif player.turns_in_prison_or_pricewar >= cfg["turns_before_forced_payment"]:
            if not self.settle(player, None, cfg["fine"], "jail_fine"):
                return False
            self._release(player, "fine")
        elif player.cash >= cfg["fine"] and self._agent.decide_pay_fine(self._view(player)):
            self.settle(player, None, cfg["fine"], "jail_fine")
            self._release(player, "fine_voluntary")
        return True

    def _release(self, player: Player, how: str) -> None:
        player.in_prison_or_pricewar = False
        player.turns_in_prison_or_pricewar = 0
        self.log("leave_jail", player.id, how=how)

    # ------------------------------------------------------------ landing
    def _land(self, player: Player) -> None:
        if player.bankrupt:
            return
        tile = self.board.tile_at(player.position)
        if isinstance(tile, OWNABLE):
            self._land_on_ownable(player, tile)
        elif tile.type == "card_draw":
            deck = self.competitor_deck if player.role == "competitor" else self.monopolist_deck
            card = deck.draw()
            self.log("card_draw", player.id, card_id=card.get("id"))
            apply_card(self, player, card)
        elif tile.type == "income_tax":
            self.settle(player, None, rules.income_tax_due(player, self.board, self.game_rules), "income_tax")
        elif tile.type == "property_tax":
            self.settle(player, None, self.game_rules["property_tax"], "property_tax")
        elif tile.type == "foundation":
            amount = rules.foundation_effect(player, self.rng, self.game_rules)
            if amount >= 0:
                self.treasurer.pay(player, amount)
                self.log("foundation", player.id, amount=amount)
            else:
                self.settle(player, None, -amount, "foundation")
        elif tile.type == "corner_role_redirect":
            self.send_to_prison(player)
        # start / corner_prison_pricewar (just visiting): nothing happens

    def _land_on_ownable(self, player: Player, tile) -> None:
        if tile.owner is None:
            if self._agent.decide_buy(tile, self._view(player)):
                price = require(tile.price, f"{tile.name} price")
                if self.treasurer.collect(player, price):
                    tile.owner = player.id
                    player.holdings.append(tile.index)
                    self.log("buy", player.id, tile=tile.index, price=price)
            return
        if tile.owner == player.id or tile.mortgaged:
            return
        owner = self._player(tile.owner)
        if owner.in_prison_or_pricewar and not self.game_rules["prison_pricewar"][f"{owner.role}_collects_rent_while_in"]:
            self.log("rent_waived", player.id, owner=owner.id, tile=tile.index)   # Rule 15
            return
        if isinstance(tile, PropertyTile):
            amount = rules.rent_due(tile, owner, self.board, self.game_rules)
        elif isinstance(tile, TransportTile):
            amount = rules.transport_fare(tile, owner, self.board)
        else:
            dice_total = sum(self.roll_dice())                  # Rule 20: a FRESH throw, not the movement roll
            self.log("utility_roll", player.id, total=dice_total)
            amount = rules.utility_charge(tile, owner, self.board, dice_total)
        self.log("rent", player.id, owner=owner.id, tile=tile.index, amount=amount)
        self.settle(player, owner, amount, "rent_payment")

    # ------------------------------------------------------------ money
    def settle(self, payer: Player, payee: Player | None, amount: int, reason: str) -> bool:
        """Pay amount to payee (None = Treasury). Liquidates assets if short; bankrupts if still short."""
        if amount <= 0:
            return True
        if payer.cash < amount:
            self._raise_cash(payer, amount)
        if payer.cash >= amount:
            if payee is None:
                self.treasurer.collect(payer, amount)
            else:
                self.treasurer.transfer(payer, payee, amount)
            self.log(reason, payer.id, amount=amount, payee=None if payee is None else payee.id)
            return True
        summary = self.treasurer.process_bankruptcy(
            payer, payee, self.board,
            resell_houses=self.game_rules["bankruptcy"]["houses_resold_to_treasury_at_half_price"])
        self.log("bankruptcy", payer.id, creditor=None if payee is None else payee.id, **summary)
        return False

    def _raise_cash(self, player: Player, needed: int) -> None:
        """Sell improvements at half price first, then mortgage unimproved holdings (largest first)."""
        while player.cash < needed:
            built = [self.board.tile_at(i) for i in player.holdings
                     if isinstance(self.board.tile_at(i), PropertyTile)
                     and self.board.tile_at(i).improvement_level > 0]
            if not built:
                break
            t = max(built, key=lambda x: x.improvement_level)
            t.improvement_level -= 1
            player.cash += require(t.house_cost, f"{t.name} house_cost") // 2
            self.log("sell_house", player.id, tile=t.index)
        while player.cash < needed:
            free = [self.board.tile_at(i) for i in player.holdings
                    if not self.board.tile_at(i).mortgaged
                    and getattr(self.board.tile_at(i), "improvement_level", 0) == 0]
            if not free:
                break
            t = max(free, key=lambda x: require(x.mortgage_value, f"{x.name} mortgage_value"))
            t.mortgaged = True
            player.cash += t.mortgage_value
            self.log("mortgage", player.id, tile=t.index, amount=t.mortgage_value)
            self._demolish_if_unmonopolized(player, getattr(t, "group", None))

    def _demolish_if_unmonopolized(self, player: Player, group) -> None:
        """Rule 12: a monopolist cannot keep houses in a city once monopolisation is lost to a mortgage.
        Houses go back to the Treasury at half price (Rule 13)."""
        if player.role != "monopolist" or group is None:
            return
        mine = [t for t in self.board.properties_in_group(group) if t.owner == player.id]
        if not mine or rules.has_monopoly(mine[0], player, self.board, self.game_rules):
            return
        for t in mine:
            if t.improvement_level > 0:
                player.cash += require(t.house_cost, f"{t.name} house_cost") * t.improvement_level // 2
                self.log("sell_house", player.id, tile=t.index, forced=True, levels=t.improvement_level)
                t.improvement_level = 0

    # ------------------------------------------------------------ agent actions
    def _try_build(self, player: Player, idx: int) -> None:
        t = self.board.tile_at(idx)
        if not isinstance(t, PropertyTile) or t.owner != player.id or t.mortgaged:
            return
        cost = require(t.house_cost, f"{t.name} house_cost")
        if t.improvement_level >= rules.max_improvement_level(t, player.role):
            return
        if (self.game_rules["building"][player.role]["requires_monopolization"]
                and not rules.has_monopoly(t, player, self.board, self.game_rules)):
            return
        if self.treasurer.collect(player, cost):
            t.improvement_level += 1
            self.log("build", player.id, tile=idx, level=t.improvement_level, cost=cost)

    def _try_mortgage_toggle(self, player: Player, idx: int) -> None:
        t = self.board.tile_at(idx)
        if not isinstance(t, OWNABLE) or t.owner != player.id:
            return
        if not t.mortgaged:
            if getattr(t, "improvement_level", 0) == 0:
                self.treasurer.pay(player, require(t.mortgage_value, f"{t.name} mortgage_value"))
                t.mortgaged = True
                self.log("mortgage", player.id, tile=idx, amount=t.mortgage_value)
                self._demolish_if_unmonopolized(player, getattr(t, "group", None))
        else:
            cost = rules.redemption_cost(t, self.game_rules)
            if self.treasurer.collect(player, cost):
                t.mortgaged = False
                self.log("unmortgage", player.id, tile=idx, amount=cost)

    # ------------------------------------------------------------ winning
    def check_winner(self) -> Player | None:
        """Game A (Rule 1): last player standing.
        Game B: ends when one whole role is eliminated; the richest survivor (Rule 25) wins."""
        alive = [p for p in self.players if not p.bankrupt]
        if len(alive) == 1:
            return alive[0]
        if self.game_rules["win_conditions"]["active_game"] == "game_b" and len({p.role for p in alive}) == 1:
            return max(alive, key=lambda p: rules.richest_score(p, self.board, self.game_rules, self.roll_dice))
        return None

    def run_game(self, agents: dict, max_turns: int = 1000) -> Player | None:
        """agents: {player_id: agent}. One 'turn' = one full round of all players.
        Returns the winner, or None if max_turns is hit first (logged as end_reason='timeout')."""
        self.log("game_start", None, roles={p.id: p.role for p in self.players},
                 mode=self.game_rules["win_conditions"]["active_game"])
        for _ in range(max_turns):
            self.turn_count += 1
            for p in self.players:
                if p.bankrupt:
                    continue
                self.run_turn(p, agents[p.id])
                winner = self.check_winner()
                if winner:
                    alive = [q for q in self.players if not q.bankrupt]
                    self.log("game_end", winner.id, rounds=self.turn_count,
                             reason="last_standing" if len(alive) == 1 else "role_eliminated")
                    return winner
        self.log("game_end", None, rounds=self.turn_count, reason="timeout")
        return None
