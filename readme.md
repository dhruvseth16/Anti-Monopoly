# Anti-Monopoly Simulation Engine

> A headless, config-driven, reproducible Python simulation of **Anti-Monopoly** (University Games official rules), run with 4 independently-parameterised AI "minds" per game, at Monte Carlo scale — to understand the mathematical balance Prof. Hentzel designed between the **Competitor** and **Monopolist** rule sets.

---

## What Is This Project?

Anti-Monopoly is a board game in which players are split into two teams with fundamentally different win conditions and economic rules:

- **Competitors** pay flat, mild rent; build freely; pay lower income tax; and collect rent even while in "Price War."
- **Monopolists** pay doubling rent once they control a colour group; must monopolise before building; pay higher income tax; and cannot collect rent while in "Prison."

The rules are precisely enough specified to simulate at scale — but nobody has run the maths to ask: *which role wins more often? Does it depend on player count? On strategy? On luck?*

This project builds a fully deterministic, seeded Python simulation engine to answer those questions. Real board data (rent tables, card decks) is being digitised from a physical copy; the engine is built against a **schema-matched placeholder dataset** so development is never blocked by missing data.

---

## Stages

| Stage | Description | Status |
|-------|-------------|--------|
| **0** | Data schema + placeholder dataset | ✅ **Done** |
| **1** | Core rules engine skeleton (role-aware, config-driven) + pytest suite foundations | ✅ **Done** |
| **2** | Implement rules engine logic (rent, tax, utility, transport, foundation, bankruptcy) + Agent architecture — 4 heuristic minds | ⏳ Up next |
| **3** | Event telemetry + single-game runner, manually validated against the rulebook | 🔲 Planned |
| **4** | Monte Carlo driver (seeded, parallel); swap in real title/card data when ready | 🔲 Planned |
| **5** | Analysis — win rate by role/agent, property ROI, luck vs. strategy attribution | 🔲 Planned |
| **6** | Scale to 5–6 players; RL agents | 🔲 Future |

### What "Done" means for Stage 1

- Every constant that is **fully specified in the rulebook** is codified in `config/game_rules.yaml` (starting cash, pass-GO, taxes, prison/price-war rules, utility multipliers, transport doubling, Foundation payouts, role-balance table, win conditions).
- All 40 board tiles are listed in `config/board.yaml` with the correct schema; rent tables for New Orleans: Basin Street (the only fully digitised property so far) are real numbers — everything else is `null` and will raise/skip at runtime.
- All engine Python modules exist with correct class/function signatures; logic stubs raise `NotImplementedError` so the test suite can mark them `xfail` until Stage 2.
- `engine/setup.py` contains the **only piece of fully working logic** in Stage 1: role-balance assignment (Rule 4) + starting-cash distribution — tested and passing.

---

## Tech Stack

| Tool | Purpose |
|------|---------|
| Python 3.11+ | Core language |
| PyYAML | Reading all config files |
| pandas + PyArrow | Telemetry event log → Parquet |
| pytest | Correctness tests (test-first approach) |
| multiprocessing | Scale-out for Monte Carlo runs |
| matplotlib + seaborn | Analysis visualisations (Stage 5) |

---

## Hard Rules (see also `agents.md`)

1. **No hardcoding** — board, card decks, and agent parameters live in `config/*.yaml`, never in `.py` files.
2. **Test first** — every rules-engine function has a pytest case before/alongside its implementation.
3. **Seeded RNG** — all randomness goes through a per-game `random.Random(seed)` instance; never the global `random` module.
4. **Atomic event logging** — log roll, buy, rent, build, trade, mortgage, bankruptcy individually; not just per-turn snapshots.
5. **Null safety** — if a config field is `null` (data not yet digitised), the engine raises or skips; it never invents numbers.

---

## Project Structure

```
Anti Monopoly/
│
├── config/                          # All game data — zero hardcoding in Python files
│   ├── board.yaml                   # The 40-tile board (see below)
│   ├── game_rules.yaml              # Every numeric constant the rulebook fully specifies
│   ├── agents.yaml                  # 4 AI mind profiles (2 competitor, 2 monopolist)
│   ├── competitor_cards.yaml        # The 25-card Competitor action deck
│   └── monopolist_cards.yaml        # The 25-card Monopolist action deck
│
├── engine/                          # Core simulation logic
│   ├── __init__.py
│   ├── board.py                     # Loads board.yaml → Tile objects; board-wide queries
│   ├── property.py                  # Dataclasses for Property, Transport, Utility tiles
│   ├── player.py                    # Player state: role, cash, position, prison/price-war
│   ├── deck.py                      # Card deck: loads YAML, shuffles, draws with cycling
│   ├── setup.py                     # Role-balance assignment (Rule 4) + player creation ✅
│   ├── treasurer.py                 # Banking: pay, collect, transfer, bankruptcy (Rule 24)
│   ├── rules.py                     # Role-specific math stubs (rent, tax, utility, etc.)
│   └── engine.py                    # Turn loop, dice, movement, win-condition stubs
│
├── agents/                          # AI decision-making
│   ├── __init__.py
│   └── base_agent.py                # Abstract interface all AI minds must implement
│
├── telemetry/                       # Event logging infrastructure
│   └── __init__.py                  # (Stage 3) will hold event_log.py + run_logger.py
│
├── sim/                             # Simulation runners
│                                    # (Stage 3) run_single_game.py — verbose single game
│                                    # (Stage 4) run_monte_carlo.py — N parallel seeded games
│
├── analysis/                        # Post-run analysis scripts
│                                    # (Stage 5) win-rate charts, ROI tables, etc.
│
├── tests/
│   ├── test_setup.py                # Role-balance + starting-cash tests (all passing ✅)
│   └── test_rules.py                # Rules engine tests (all xfail pending Stage 2)
│
├── agents.md                        # Coding rules for AI agents working on this repo
├── requirements.txt                 # Python dependencies
└── .gitignore                       # Excludes .venv, __pycache__, *.parquet, etc.
```

---

## File-by-File Explanation

### `config/board.yaml`
The complete 40-tile board, one YAML entry per tile. Each tile has a `type` field (`start`, `property`, `transport`, `utility`, `card_draw`, `income_tax`, `property_tax`, `corner_prison_pricewar`, `corner_role_redirect`, `foundation`) and then type-specific fields.

For **property** tiles the schema includes:
- `price` — purchase price
- `house_cost` — cost per improvement level
- `mortgage_value` / `mortgage_redemption` — per Rule 12
- `rent.competitor` — list of 6 rents: [0 houses, 1, 2, 3, 4 houses, 1 apartment]
- `rent.monopolist` — list of 5 rents: [0 houses, 1, 2, 3 houses, 1 apartment]
- `monopolist_unbuilt_rent_if_monopolized` — the Rule 10 doubled unimproved rent

Currently **only New Orleans: Basin Street** (index 1) has real numbers from the physical card. All other properties have `null` rent tables and will be filled in as the physical copy is digitised. The Electric Company utility (index 12) also has real `dice_multiplier` values.

For **transport** tiles (4 railroads/companies), the fare tables show the Competitor's flat $20 and the Monopolist's doubling progression ($40 → $80 → $160 → $320).

### `config/game_rules.yaml`
Every constant the rulebook fully specifies, regardless of which properties are digitised:
- **Starting cash**: $1,500 per player in exact bill denominations (Rule 5)
- **Pass GO**: $100 (Rule 14)
- **Income tax** (Rule 17): pay the cheaper of $200 flat or a percentage formula — 10%+10%+10% for Competitors, 20%+10%+10% for Monopolists
- **Property tax**: $75 flat for everyone (Rule 18)
- **Prison / Price War** (Rule 15): $50 fine, must pay before 3rd turn if no doubles; Monopolists cannot collect rent while imprisoned
- **Doubles** (Rule 7): extra turn granted, but never chains further
- **Transport** (Rule 19): Competitor pays flat 10% of purchase price; Monopolist fare doubles per company owned
- **Utilities** (Rule 20): 4× dice for everyone when Competitor owns; 4× or 10× when Monopolist owns both
- **Foundation** (Rule 21): Competitor rolls die — 1→$25, 2→$50, other→$0; Monopolist pays $160 flat
- **Building** (Rule 11): Competitors can build up to 4 houses then 1 apartment without monopolising; Monopolists require a monopoly first and max out at 3 houses + 1 apartment
- **Mortgage** (Rule 12): half of purchase price; redemption observed as ~110% of mortgage value
- **Bankruptcy** (Rule 24): houses resold to treasury at half price before asset transfer
- **Role balance** (Rule 4): even player counts split evenly; odd counts differ by at most 1
- **Win conditions** (Rule 1): Game A = last player standing; Game B = richest survivor per role

### `config/agents.yaml`
Four AI personality profiles — two Competitors and two Monopolists — matching the Rule 4 balance requirement exactly for 4-player games (for 3-player, drop any one):
- **`aggressive_monopolist`** — zero cash floor, overvalues expensive groups, builds immediately
- **`conservative_competitor`** — $800 cash buffer, only buys above an ROI threshold, builds slowly
- **`balanced_monopolist`** — $300 buffer, moderate trade aggression, builds hard once stable
- **`opportunistic_competitor`** — $100 floor, prioritises cheap groups for fast early builds, moderate trade aggression

Parameters here drive the heuristic agent logic that will be implemented in Stage 2.

### `config/competitor_cards.yaml`
The Competitor action deck — 25 cards total, only 1 digitised so far (`comp_001`: collect $25 from treasury). The remaining 24 are commented-out stubs (`comp_002` through `comp_025`) ready to be filled in as the physical cards are transcribed. Effect types are an open vocabulary (`collect`, `move_to`, `move_relative`, `go_to_prison`, `get_out_free`, `pay_per_house`, etc.).

### `config/monopolist_cards.yaml`
The Monopolist action deck — same structure as above. 1 digitised (`mono_001`: collect $75 from treasury), 24 stubs waiting.

---

### `engine/property.py`
Defines the **dataclasses** that represent board tiles in memory:
- `Tile` — base class for all 40 tiles (index, type, name, group, price)
- `PropertyTile(Tile)` — adds rent tables for both roles, improvement level (0–5), mortgage and ownership state
- `TransportTile(Tile)` — adds role-split fare tables, ownership, mortgage state
- `UtilityTile(Tile)` — adds role-split dice-multiplier tables, ownership, mortgage state

These are plain `@dataclass` objects with no logic — they are pure state containers.

### `engine/board.py`
Loads `config/board.yaml` and builds a list of `Tile` objects (one per board position). Handles the YAML flattening needed to map nested `rent.competitor` / `rent.monopolist` keys into the flat `rent_competitor` / `rent_monopolist` dataclass fields.

Public interface:
- `tile_at(index)` — wraps index modulo board length (for passing GO)
- `properties_in_group(group)` — returns all `PropertyTile` objects in a colour group
- `owned_count_in_group(group, player_id)` — how many properties in a group a player owns (used for monopoly detection and transport fare calculation)

### `engine/player.py`
The `Player` dataclass — runtime state for one player:
- `id`, `role` (`"competitor"` | `"monopolist"`), `cash`, `position`
- `in_prison_or_pricewar`, `turns_in_prison_or_pricewar` — Rule 15 state machine
- `holdings` — list of tile indices owned
- `bankrupt` — flag set by the treasurer on Rule 24 resolution
- `pawn_color` property — green for Competitors, blue for Monopolists (Rule 6)

### `engine/deck.py`
Loads a card deck YAML file, shuffles it using the game's seeded RNG, and exposes a `draw()` method that cycles — drawn cards go to the bottom of the deck (Rule 16), so the deck never runs out.

### `engine/setup.py`
**The only fully working logic module in Stage 1.** Implements:
- `assign_roles(num_players, rng)` — Rule 4 role-balance: even split for even counts; random extra seat for odd counts; result is shuffled so no seat is biased
- `starting_cash_total(game_rules)` — reads $1,500 from config
- `create_players(num_players, rng, game_rules)` — combines the two functions above and returns a list of `Player` objects ready to play

### `engine/treasurer.py`
Handles all money movement so no module does raw `player.cash +=` math directly:
- `pay(player, amount)` — bank pays a player (pass GO, card reward, etc.)
- `collect(player, amount)` — player pays the bank; returns `False` if they can't cover it (caller triggers asset sale or bankruptcy)
- `transfer(payer, payee, amount)` — player-to-player payment (rent, etc.)
- `process_bankruptcy(bankrupt, creditor)` — **stub** for Stage 2: Rule 24 sequence (sell houses at half price, transfer all assets to creditor or treasury)

### `engine/rules.py`
Stub module containing the **function signatures** for all role-specific calculations. Each function raises `NotImplementedError` until Stage 2, and each has a corresponding `xfail` test in `tests/test_rules.py` that encodes the exact expected output from the rulebook:
- `rent_due(tile, owner)` — Rules 9, 10, 11 (includes monopolised-unbuilt doubling)
- `transport_fare(tile, owner, board)` — Rule 19
- `utility_charge(tile, owner, board, dice_roll)` — Rule 20
- `income_tax_due(player, board, rules_config)` — Rule 17
- `foundation_effect(player, rng, rules_config)` — Rule 21

### `engine/engine.py`
The top-level `Engine` class that will run a full game. Receives all dependencies via constructor (players, board, decks, treasurer, RNG, rules config) for clean testability. Currently contains:
- `roll_dice()` — **working**: rolls two dice using the seeded `rng`
- `run_turn(player, agent)` — **stub** (Stage 2+): movement, landing resolution, agent decisions
- `check_winner()` — **stub** (Stage 2+): Game A / Game B win conditions
- `run_game(max_turns)` — **stub** (Stage 2+): full turn loop

---

### `agents/base_agent.py`
Abstract base class that every AI mind must implement. Defines the four decision points an agent is asked about each turn:
- `decide_buy(tile, state) → bool` — should the agent buy the property it just landed on?
- `decide_build(state) → list` — which properties to add a house/apartment to this turn?
- `decide_trade(state) → list` — any trades to propose this turn?
- `decide_mortgage(state) → list` — which properties to mortgage or unmortgage?

Concrete implementations (e.g. `heuristic_agent.py`) will be added in Stage 2, reading their personality parameters from `config/agents.yaml`.

---

### `telemetry/` *(Stage 3)*
Planned home for the event logging system:
- `event_log.py` — defines the schema for atomic events: `game_id`, `turn`, `player_id`, `event_type`, `payload`
- `run_logger.py` — writes event streams to Parquet files via pandas + PyArrow

### `sim/` *(Stages 3–4)*
Planned simulation runners:
- `run_single_game.py` — one verbose game with full console output for manual rulebook validation
- `run_monte_carlo.py` — N seeded parallel games using `multiprocessing`, writing Parquet output for Stage 5 analysis

### `analysis/` *(Stage 5)*
Planned analysis scripts:
- Win rate by role and by agent personality
- Property ROI tables (which colour groups pay off fastest?)
- Luck vs. strategy attribution

---

### `tests/test_setup.py`
**All tests passing ✅** — covers the one working logic module:
- 4-player role split is exactly 2 + 2
- 3-player role split differs by at most 1
- Same seed always produces the same role assignment
- Player counts outside 2–6 are rejected
- Every player starts with $1,500
- Pawn colour matches role (green = Competitor, blue = Monopolist)

### `tests/test_rules.py`
**All tests `xfail` pending Stage 2** — correctness targets written before the logic exists:
- Basin Street Competitor rent with 0 houses → $6 (Rule 9)
- Basin Street Monopolist unimproved rent when monopolised → $12 (Rule 10)
- Monopolist rent is exactly double Competitor per improvement tier (Rule 10)
- Competitor transport fare is flat $20 regardless of railroads owned (Rule 19)
- Monopolist transport fare doubles: $40 → $80 → $160 → $320 (Rule 19)
- Competitor utility is always 4× dice, even when owning both (Rule 20)
- Monopolist utility is 10× dice when owning both (Rule 20)
- Competitor income tax picks the cheaper of $200 or 10%+10%+10% (Rule 17)
- Monopolist income tax picks the cheaper of $200 or 20%+10%+10% (Rule 17)

---

### `agents.md`
Coding rules file read by AI coding agents working in this repo. Enforces: no hardcoding, test-first for every rules function, seeded RNG only, atomic event logging. Also records the current development stage so an agent always knows where the codebase is.

### `requirements.txt`
Python dependencies: `pyyaml`, `pandas`, `pyarrow`, `pytest`, `matplotlib`, `seaborn`.

### `.gitignore`
Excludes `.venv/`, `__pycache__/`, `*.pyc`, `.pytest_cache/`, `*.parquet` (generated telemetry files), and `.DS_Store`.

---

## Running Tests

```bash
# From the project root, with the venv activated:
pytest tests/
```

Expected output right now: all `test_setup.py` tests **PASS**; all `test_rules.py` tests **XFAIL** (expected — logic not yet implemented).

---

## Data Digitisation Status

| Item | Status |
|------|--------|
| New Orleans: Basin Street rent tables | ✅ Real data |
| Electric Company dice multipliers | ✅ Real data |
| U.S. Railroad fare tables | ✅ Real data |
| Remaining 25 properties | ⏳ `null` — pending physical card transcription |
| Remaining 3 transport tiles | ⏳ Partially `null` |
| U.S. Gas Company multipliers | ⏳ `null` |
| Competitor card deck | ⏳ 1/25 digitised |
| Monopolist card deck | ⏳ 1/25 digitised |