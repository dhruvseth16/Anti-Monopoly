# Anti-Monopoly Simulation Engine — Project Summary (after Stage 4)

Headless, seeded, config-driven Python simulation of *Anti-Monopoly* (University Games rules). Four heuristic
"minds" per game (2 Competitors + 2 Monopolists), Monte Carlo scale.
All numbers in section 6 come from `python -m tools.sim_audit` (seeded, so you get the same numbers on your PC).

---

## 1. Where we are

| Stage | What | State |
|---|---|---|
| 0–1 | Schema, placeholder data, engine skeleton, role assignment (`setup.py`) | done |
| 2 | Rules math (rent, tax, fares, foundation), bankruptcy, turn loop, jail, cards, heuristic agents | done |
| 3 | Event log → Parquet, one-game runner with play-by-play, config validator | done |
| 4 | Parallel seeded Monte Carlo driver, manifest, refuses incomplete data | done |
| data | All 28 title cards + 50 action cards digitised; validator: 0 errors / 0 warnings / 0 pending | done |
| 5 | Analysis (ROI, luck vs strategy, charts) | next — *after* agents are fixed (see §8) |

## 2. Architecture

```
config/*.yaml ──► sim/game_factory.build_game(seed) ──► Engine + {player_id: agent}
 board, rules,          │  one random.Random(seed) feeds roles, deck shuffles, dice, foundation
 agents, 2 decks        ▼
                 Engine.run_game(agents, max_rounds)
                   loop rounds → run_turn → _play_roll → move → _land → settle/cards → agent hooks
                        │ every action appends a dict to engine.events  (atomic log, Hard Rule 4)
                        ▼
        telemetry/ (events → Parquet)      sim/run_monte_carlo (N games, Pool, summary.parquet, manifest.json)
```

| Module | Responsibility | Key functions |
|---|---|---|
| `engine/property.py` | Plain dataclasses: `Tile`, `PropertyTile`, `TransportTile`, `UtilityTile` (owner, improvement_level, mortgaged) | – |
| `engine/board.py` | Loads `board.yaml`, flattens nested rent/fare/dice keys | `tile_at`, `properties_in_group`, `owned_count_in_group` |
| `engine/player.py` | `Player`: role, cash, position, prison state, holdings, bankrupt, get_out_free_cards | `pawn_color` |
| `engine/setup.py` | Rule 4 role balance, Rule 5 start cash | `assign_roles`, `create_players` |
| `engine/deck.py` | Seeded shuffle, draw → bottom of deck (Rule 16) | `Deck.draw` |
| `engine/rules.py` | **Pure maths**, no state changes: Rules 9-12, 17, 19-21, 25 | `rent_due`, `transport_fare`, `utility_charge`, `income_tax_due`, `foundation_effect`, `has_monopoly`, `redemption_cost`, `richest_score`, `net_worth` |
| `engine/treasurer.py` | Money movement + Rule 24 bankruptcy | `pay`, `collect`, `transfer`, `process_bankruptcy` |
| `engine/cards.py` | One handler per card effect type (open vocabulary) | `apply_card`, handlers: `none, collect, pay, conditional_collect, move_to, go_to_prison, collect_from_each_monopolist, …` |
| `engine/engine.py` | Turn loop, movement, landing, jail, liquidation, build/mortgage execution, winner check | `run_game`, `run_turn`, `_play_roll`, `move_by`, `move_to`, `_land`, `_land_on_ownable`, `settle`, `_raise_cash`, `_try_build`, `_try_mortgage_toggle`, `_demolish_if_unmonopolized`, `check_winner` |
| `agents/base_agent.py` | Interface: `decide_buy`, `decide_build`, `decide_trade`, `decide_mortgage`, `decide_pay_fine` | – |
| `agents/heuristic_agent.py` | The one mind used by all 4 profiles (parameters from `agents.yaml`) | see §5 |
| `agents/factory.py` | Matches profiles in `agents.yaml` to players by role | `load_agents` |
| `sim/game_factory.py` | Wires one complete seeded game | `build_game` |
| `sim/run_single_game.py` | One game with human-readable play-by-play (rulebook checking) | `describe`, `run` |
| `sim/run_monte_carlo.py` | N games, multiprocessing, Wilson CIs, refuses incomplete data | `run`, `play_one`, `report`, `preflight` |
| `telemetry/` | `events_to_frame`, `write_events`, `summarize_game` → Parquet | – |
| `tools/validate_config.py` | Duplicate-YAML-key detection, rulebook cross-checks, card checks | `run_checks` |
| `tools/sim_audit.py` | Prints the calibration numbers in §6 | `audit` |

Hard rules still enforced: no game data in `.py`; null ⇒ `MissingDataError` (never invented); one seeded RNG; atomic events; test-first (125 tests).

## 3. One turn, step by step (what the engine really does)

1. **Jail check (Rule 15).** If imprisoned / in price war: use a get-out-free card (none exist in the decks); else after 2 failed
   turns pay $50 *before* rolling; else the agent may pay $50 voluntarily (`decide_pay_fine`).
2. **Roll 2 dice** from the seeded RNG. In jail, doubles free the player (Rule 15C-1) and the move proceeds.
3. **Move** clockwise; passing or landing on Start pays $100 (Rule 14).
4. **Landing resolution** by tile type:
   - unowned street / transport / utility → `agent.decide_buy`; if yes pay the printed price (no auction, Rule 9)
   - owned by another, unmortgaged → charge. Streets: `rent_due` (role ladder; doubled unbuilt rent if the owner is a monopolist with ≥2 unmortgaged streets in the city). Transport: `transport_fare`. Utility: **a fresh 2-dice throw** × multiplier (Rule 20). No rent if the owner is a jailed monopolist (Rule 15B).
   - card square → draw from *your role's* deck, apply effect, card to the bottom
   - income tax: min($200, role %), property tax $75, foundation (competitor rolls 1 die: 1→$25, 2→$50; monopolist pays $160)
   - go-to-prison corner → pawn to the prison/price-war square, no Start money (Rule 15B)
5. **Payment shortfall → forced liquidation** (`settle` → `_raise_cash`), see §5. Still short ⇒ bankruptcy (Rule 24).
6. **Agent actions after moving:** build (`decide_build`), redeem mortgages (`decide_mortgage`). Trading is **not called** (stub).
7. **Doubles (Rule 7):** exactly one extra turn; the extra turn's doubles never chain.
8. **Winner check** after every turn: Game A = last player standing; Game B = ends when a whole role is eliminated, richest survivor wins (Rule 25).

## 4. Why 200+ games take seconds when a real game takes ~3 hours

A physical game is slow because of **people**, not because of dice or rules: counting bills, deciding, reading cards, talking, trading.
The simulation does only the rule arithmetic.

- One simulated game ≈ **800 dice rolls** (~210 rounds × 4 players) and ~2,800 logged events.
- That costs ≈ **56 ms** of CPU (≈ 14,000 rolls/second per core). Your PC: 2,000 games in 155 s on 4 workers.
- The same 800 turns at 20–60 s each are **4.5–13 hours** of human play (table in §6). So the sim is not skipping *game*; it skips *thinking time*.
- Your early progress lines ("200 games in 22 s") include Windows process start-up; the slow tail (last 400 games took ~100 s) is the
  games that run to the 600-round cap.

## 5. Assumptions, simplifications and agent behaviour

### 5.1 Engine simplifications (each one can change results)

| # | Rule | What the sim does | Effect |
|---|---|---|---|
| A1 | 9 | No auctions; declined property just stays unowned (matches the rulebook) | none |
| A2 | 23 | **No trading at all.** `decide_trade` is never called | **High.** Rulebook tells competitors to trade to block monopolies |
| A3 | – | Agents buy **only** the street they land on, only on landing | matches rules, but no deal-making |
| A4 | 12/13 | Agents **never** mortgage or sell houses to *fund* a purchase or build; liquidation only happens when a **debt can't be paid** | **High.** Humans mortgage to buy up property (the rulebook's competitor strategy) |
| A5 | 24 | Liquidation is automatic: sell houses at half price (highest level first) → mortgage unimproved tiles (largest mortgage value first) → bankrupt | agents have no say |
| A6 | 12 | A monopolist who mortgages a city street loses monopolisation; all houses in that city are sold at half price | per rulebook |
| A7 | 6/8 | Seat order is fixed 0..n-1 (roles shuffled across seats); no starting dice-off | none statistically |
| A8 | 5/2 | Money is a plain integer: no bills, no making change, treasurer is the engine | none |
| A9 | 22 | Unlimited houses/apartments (rule says make more) | faithful |
| A10 | 11 | Apartment = one more build step costing `house_cost` (confirmed by you); houses are not refunded on upgrade | faithful |
| A11 | 20 | Utility: new throw of **2 dice** each landing (your confirmation) | – |
| A12 | cards | `mono_003/017 miss_turns_collecting_rent: 2` is informational: normal prison rules apply (your confirmation) | – |
| A13 | 15 | Entering prison on a doubles roll cancels the extra turn | assumption, minor |
| A14 | – | Agents see all public state; no hidden information, no bluffing, no emotion | – |
| A15 | – | **Timeout:** a game with no winner after `max_rounds` is logged `end_reason=timeout` and excluded from win-rate denominators | see §6 |

### 5.2 What each mind does

All four use the same code (`HeuristicAgent`) with different parameters; the *role* changes what is legal.

| Profile | Role | cash_floor | Buys | Builds |
|---|---|---|---|---|
| aggressive_monopolist | Monopolist | $0 | any title it can afford; price/1.3 for the top-third dearest cities (Washington, S.F., N.Y.) | immediately, as many as cash allows |
| balanced_monopolist | Monopolist | $300 | keep $300 after buying | waits until cash ≥ $600, then builds hard down to $300 |
| conservative_competitor | Competitor | $800 | only if $800 remains afterwards (the ROI gate is **inactive**: no `roi_threshold` in `agents.yaml`) | at most 1 house per turn, keeps $800 |
| opportunistic_competitor | Competitor | $100 | price/1.4 for the cheapest third (New Orleans, L.A., Chicago) | immediately |

Every turn, every agent:
- **Buy**: yes if `cash ≥ price` and `cash − price/multiplier ≥ cash_floor`.
- **Build**: considers its unmortgaged streets; competitors may build on any street, monopolists only where they own ≥2 unmortgaged streets in the city.
  Picks the lowest-level, cheapest street first (even building), repeats while cash after cost ≥ floor. Max level: competitor 4 houses + apartment, monopolist 3 + apartment.
- **Mortgage**: only *redeems* mortgaged tiles (cheapest first) while cash stays above the floor. Never mortgages voluntarily.
- **Fine**: monopolists pay the $50 early whenever cash − 50 ≥ floor (they earn nothing in prison); competitors wait for doubles or the forced payment (they still collect rent).
- **Trade**: nothing.

Answers to your direct questions: *No — agents do not mortgage or sell houses to raise money for buying or building.* They do both
**only when forced** to pay rent, tax, a fine or a card debt, and then houses go back at **half value** (Rule 13) before any mortgage.

## 6. The numbers (250 games, 4 players, seeds 0–249, default agents, 600-round cap)

| Measure | Result |
|---|---|
| Speed | 56 ms/game, 803 dice rolls/game, 2,849 events/game |
| Rounds per finished game | mean 212 · median 185 · p10 104 · p90 370 · max 577 · min 42 |
| Player-turns per game | mean 803 · median 728 |
| Equivalent human time | at 30 s/turn ≈ 6.1 h median · at 20 s ≈ 4.0 h |
| 3 players / 2 players, median rounds | 218 / 206 |
| Timeouts | 2.4 % (your 2,000-game run: 3.2 %). 600 rounds = 2,400 turns |
| Who is alive at a timeout | mostly **two competitors** (4 of 6): neither can bankrupt the other |
| Dice | 200,864 rolls: doubles 16.61 % (fair 16.67 %), χ² = 3.9 (limit 18.3) → **fair**, not biased |
| Landings | uniform 2.5 %; Start 3.2 % and tiles 12 / 29 ≈ 3.1 % (two card decks send pawns there) |
| Titles owned after round 3 / 5 / 10 / 20 / 40 | 8.3 / 11.4 / 15.5 / 18.3 / 20.5 of 28 |
| Board fully sold | median round 164, **and only in 43 % of games** |
| First bankruptcy | median round 90 (p10 53, p90 151) |

Per game, summed over the 2 players of each role:

| Action | Competitors | Monopolists |
|---|---|---|
| Titles bought | 9.3 | 18.2 |
| Houses/apartments built | 48.0 | 55.6 |
| Houses sold under forced liquidation | 36.2 | 25.5 |
| Mortgages (forced) / redemptions | 7.7 / 1.5 | 12.0 / 8.8 |
| Bankruptcies | 1.8 | 1.2 |
| Sent to prison/price war | 16.1 | 13.6 |
| Paid $50 fine: voluntary / forced | 0 / 11.1 | 7.6 / 4.0 |

**Randomness:** every random event (roles, deck order, dice, foundation die, utility/card dice) comes from one `random.Random(seed)`
(Mersenne Twister, uniform `randint(1,6)`). Nothing is biased towards ending games sooner; the dice table above is the check.

## 7. How to compare with real play (measure these on your table)

Count in one or two real games and compare with the sim column:

| Real-game measurement | Sim today |
|---|---|
| Rounds (full laps of all players) until someone goes bankrupt | median 90 |
| Rounds until the board is fully sold | median 164, often never |
| Titles owned after round 10 | 15.5 / 28 |
| Total rounds in a game | median 185 (≈ 730 player-turns) |
| Times someone is sent to prison/price war per game | ~30 |
| Who wins, and how | Monopolists 85 %, Competitors 15 % |

Your 3-hour estimate: 3 h at ~30 s/turn ≈ 360 turns ≈ **90 rounds**. The sim's games are ~2× longer, and its board
sells out far more slowly than a real table would. Both point at the agents (below), not at the dice.

## 8. What the numbers say, and next steps

1. **Agents are too passive buyers.** 57 % of games never sell all 28 titles; competitors buy half as many as monopolists.
   `conservative_competitor` (floor $800) wins 1.8 %: its floor starves it, which is the opposite of the rulebook's competitor advice.
2. **Over-building then fire-selling.** Competitors build 48 and are forced to sell 36 houses at half price: a buffer problem, not a rules problem.
3. **Two-competitor stalemates** explain most timeouts in Game A. Game B (ends when a role is eliminated) or the Two-Hour rule avoids this.
4. **Balance test (done):** with monopolist rents set equal to competitor rents the sim is ≈ 48 / 52, so the engine adds no hidden bias.
   The 85 / 15 split comes from the doubled rents/fares + 2-street monopolisation meeting passive, trade-less play.
5. **Fix order:** (a) agents that buy aggressively, mortgage to fund purchases and keep a build buffer, (b) trading (Rule 23),
   (c) re-run Monte Carlo, (d) only then Stage 5 analysis.
