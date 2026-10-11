"""One heuristic mind, parameterised by a profile from config/agents.yaml.

Profile keys used: cash_floor, property_valuation_multiplier{default, high_price_groups,
cheap_groups, roi_weighted}, build_priority (immediate | slow | late_aggressive).
Optional key: roi_threshold (rent[0] / price) - used only when roi_weighted is true.
Price tiers are DERIVED from the board (top / bottom third of colour groups by average price).
"""
from __future__ import annotations

import math

from engine import rules
from engine.property import PropertyTile
from .base_agent import BaseAgent


class HeuristicAgent(BaseAgent):
    # ---- helpers
    def _tiers(self, board) -> tuple[set, set]:
        avg = {}
        for t in board.tiles:
            if isinstance(t, PropertyTile) and t.group and t.price is not None:
                avg.setdefault(t.group, []).append(t.price)
        ranked = sorted(avg, key=lambda g: sum(avg[g]) / len(avg[g]))
        k = max(1, math.ceil(len(ranked) / 3))
        return set(ranked[:k]), set(ranked[-k:])          # cheap, high

    def _multiplier(self, tile, board) -> float:
        cfg = self.params.get("property_valuation_multiplier", {})
        m = cfg.get("default", 1.0)
        if tile.group:
            cheap, high = self._tiers(board)
            if tile.group in high:
                m = cfg.get("high_price_groups", m)
            elif tile.group in cheap:
                m = cfg.get("cheap_groups", m)
        return m

    # ---- decisions
    def decide_buy(self, tile, state) -> bool:
        if tile.price is None:
            return False
        p = state.player
        if p.cash < tile.price:
            return False
        effective_price = tile.price / self._multiplier(tile, state.board)
        if p.cash - effective_price < self.params["cash_floor"]:
            return False
        cfg = self.params.get("property_valuation_multiplier", {})
        threshold = self.params.get("roi_threshold")
        if cfg.get("roi_weighted") and threshold is not None and isinstance(tile, PropertyTile):
            rents = tile.rent_competitor if p.role == "competitor" else tile.rent_monopolist
            if rents is not None and rents[0] / tile.price < threshold:
                return False
        return True

    def decide_build(self, state) -> list:
        p, board = state.player, state.board
        prio = self.params["build_priority"]
        floor = self.params["cash_floor"]
        if prio == "late_aggressive" and p.cash < 2 * floor:      # keeps a buffer until stable
            return []
        needs_monopoly = state.rules["building"][p.role]["requires_monopolization"]
        limit = 1 if prio == "slow" else 99

        cands = []
        for idx in p.holdings:
            t = board.tile_at(idx)
            if not isinstance(t, PropertyTile) or t.mortgaged or t.house_cost is None:
                continue
            rents = t.rent_competitor if p.role == "competitor" else t.rent_monopolist
            if rents is None:
                continue
            if needs_monopoly and (t.group_size is None or not rules.has_monopoly(t, p, board, state.rules)):
                continue
            cands.append([t, t.improvement_level, len(rents) - 1])

        plan, cash = [], p.cash
        while len(plan) < limit:
            options = [c for c in cands if c[1] < c[2] and cash - c[0].house_cost >= floor]
            if not options:
                break
            best = min(options, key=lambda c: (c[1], c[0].house_cost))   # level-first = even building
            best[1] += 1
            cash -= best[0].house_cost
            plan.append((best[0].index, "build"))
        return plan

    def decide_trade(self, state) -> list:
        return []     # stubbed until stage 3

    def decide_mortgage(self, state) -> list:
        """Redeem mortgages (cheapest first) only when cash stays above the floor."""
        p, board = state.player, state.board
        cash, out = p.cash, []
        owned = [board.tile_at(i) for i in p.holdings]
        for t in sorted((t for t in owned if t.mortgaged and t.mortgage_value is not None),
                        key=lambda t: rules.redemption_cost(t, state.rules)):
            cost = rules.redemption_cost(t, state.rules)
            if cash - cost >= self.params["cash_floor"]:
                cash -= cost
                out.append(t.index)
        return out
