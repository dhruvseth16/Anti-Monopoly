"""One verbose, seeded game for validating the engine against the rulebook by eye.

  python -m sim.run_single_game --seed 1 --players 4
  python -m sim.run_single_game --seed 1 --mode game_b --out out/game1.parquet
  python -m sim.run_single_game --seed 1 --placeholder-fill      # before digitisation is finished
"""
from __future__ import annotations

import argparse
import sys

from engine.errors import MissingDataError
from telemetry.run_logger import summarize_game, write_events, write_summaries
from .game_factory import build_game
from .placeholder_fill import BANNER


def _tile(board, idx) -> str:
    t = board.tile_at(idx)
    return f"{t.name or t.type} [{idx}]"


def describe(ev: dict, board) -> str | None:
    """One human sentence per event. Returns None for events that would only duplicate another line."""
    e, p = ev["event"], f"P{ev['player_id']}"
    if e == "rent_payment":
        return None                                  # already narrated by the preceding 'rent' event
    table = {
        "game_start": lambda: f"GAME START ({ev['mode']}) roles={ev['roles']}",
        "roll": lambda: f"{p} rolls {ev['dice'][0]}+{ev['dice'][1]}" + ("  DOUBLES" if ev['dice'][0] == ev['dice'][1] else ""),
        "move": lambda: f"  {p} moves to {_tile(board, ev['to'])}",
        "pass_go": lambda: f"  {p} collects ${ev['amount']} for START",
        "buy": lambda: f"  {p} BUYS {_tile(board, ev['tile'])} for ${ev['price']}",
        "rent": lambda: f"  {p} owes ${ev['amount']} to P{ev['owner']} at {_tile(board, ev['tile'])}",
        "rent_waived": lambda: f"  {p} pays nothing: owner P{ev['owner']} is jailed (Rule 15B)",
        "utility_roll": lambda: f"  {p} throws {ev['total']} for the utility (Rule 20)",
        "build": lambda: f"  {p} BUILDS on {_tile(board, ev['tile'])} -> level {ev['level']} (${ev['cost']})",
        "mortgage": lambda: f"  {p} mortgages {_tile(board, ev['tile'])} for ${ev['amount']}",
        "unmortgage": lambda: f"  {p} redeems {_tile(board, ev['tile'])} for ${ev['amount']}",
        "sell_house": lambda: f"  {p} sells improvements on {_tile(board, ev['tile'])} at half price",
        "income_tax": lambda: f"  {p} pays income tax ${ev['amount']}",
        "property_tax": lambda: f"  {p} pays property tax ${ev['amount']}",
        "foundation": lambda: f"  {p} receives ${ev['amount']} from the Foundation" if ev.get("amount") else f"  {p} gets nothing from the Foundation",
        "card_collect": lambda: f"  {p} collects ${ev['amount']} (card)",
        "card_pay": lambda: f"  {p} pays ${ev['amount']} (card)",
        "card_pay_per_house": lambda: f"  {p} pays ${ev['amount']} repairs (card)",
        "card_collect_from_player": lambda: f"  {p} pays ${ev['amount']} to P{ev['payee']} (card)",
        "card_get_out_free": lambda: f"  {p} keeps a get-out-free card",
        "card_draw": lambda: f"  {p} draws card {ev['card_id']}",
        "go_to_prison": lambda: f"  {p} is sent to PRISON / PRICE WAR (no START money)",
        "leave_jail": lambda: f"  {p} leaves prison/price war via {ev['how']}",
        "jail_fine": lambda: f"  {p} pays the ${ev['amount']} fine",
        "bankruptcy": lambda: f"  *** {p} BANKRUPT -> creditor {ev['creditor']} (houses resold for ${ev['houses_resold_for']}, cash moved ${ev['cash_transferred']}, tiles {ev['tiles']})",
        "game_end": lambda: f"GAME END after {ev['rounds']} rounds: winner {'P' + str(ev['player_id']) if ev['player_id'] is not None else 'none'} ({ev['reason']})",
    }
    fn = table.get(e)
    return fn() if fn else f"  {p} {e} { {k: v for k, v in ev.items() if k not in ('turn', 'event', 'player_id')} }"


def run(seed: int, players: int, max_rounds: int, mode: str | None, out: str | None,
        placeholder_fill: bool, quiet: bool, config_dir: str = "config"):
    engine, agents = build_game(seed, players, config_dir, mode, placeholder_fill)
    if placeholder_fill:
        print(BANNER)
    winner = engine.run_game(agents, max_rounds)
    game_id = f"seed{seed}"
    if not quiet:
        last_round = -1
        for ev in engine.events:
            if ev["turn"] != last_round and ev["event"] != "game_end":
                last_round = ev["turn"]
                print(f"\n--- round {last_round} ---")
            line = describe(ev, engine.board)
            if line:
                print(line)
    summary = summarize_game(engine, winner, seed, agents, game_id)
    print("\nSUMMARY", summary)
    print("FINAL  ", {p.id: dict(role=p.role, cash=p.cash, tiles=len(p.holdings), bankrupt=p.bankrupt)
                      for p in engine.players})
    if out:
        write_events(engine.events, game_id, out)
        write_summaries([summary], str(out).replace(".parquet", "_summary.parquet"))
        print(f"wrote {out} and *_summary.parquet")
    return engine, winner, summary


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--players", type=int, default=4)
    ap.add_argument("--max-rounds", type=int, default=300)
    ap.add_argument("--mode", choices=["game_a", "game_b"], default=None, help="override win_conditions.active_game")
    ap.add_argument("--out", default=None, help="write the event log to this .parquet path")
    ap.add_argument("--placeholder-fill", action="store_true", help="fill null tile fields with SYNTHETIC numbers")
    ap.add_argument("--quiet", action="store_true", help="summary only, no play-by-play")
    a = ap.parse_args(argv)
    try:
        run(a.seed, a.players, a.max_rounds, a.mode, a.out, a.placeholder_fill, a.quiet)
    except MissingDataError as exc:
        print(f"\nSTOPPED: {exc}\nThis game reached a field that is not digitised yet. Run `python -m tools.validate_config`"
              " to see what is missing, or re-run with --placeholder-fill for a plumbing check.")
        sys.exit(2)


if __name__ == "__main__":
    main()
