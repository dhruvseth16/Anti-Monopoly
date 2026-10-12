"""Seeded, parallel Monte Carlo driver.

  python -m sim.run_monte_carlo --games 2000 --players 4 --workers 6 --out-dir out/run1
  python -m sim.run_monte_carlo --games 500 --mode game_b --seed-start 10000 --events-every 100

Reproducibility: game i uses seed (seed_start + i) and nothing else, so results are identical for any
--workers value and any re-run. Outputs in --out-dir:
  summary.parquet   one row per game (win role/agent, rounds, end reason, ...)
  manifest.json     arguments, config file hashes, data-completeness flag, timing, git commit
  events/*.parquet  full atomic event logs for every Nth game (--events-every), none by default

Real runs are REFUSED until config/ is fully digitised and valid (a partly-null deck would silently
bias results). --placeholder-fill or --allow-incomplete override that and tag the manifest accordingly.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import subprocess
import sys
import time
from multiprocessing import Pool
from pathlib import Path

import pandas as pd
import yaml

from engine.errors import MissingDataError
from telemetry.run_logger import summarize_game, write_events, write_summaries
from tools.validate_config import run_checks
from .game_factory import build_game
from .placeholder_fill import BANNER

CONFIG_FILES = ["board.yaml", "game_rules.yaml", "agents.yaml", "competitor_cards.yaml", "monopolist_cards.yaml"]


# ------------------------------------------------------------------ worker
def play_one(job: tuple[int, dict]) -> dict:
    """Top-level (picklable) so it works with Windows 'spawn'. Never shares state between games."""
    seed, cfg = job
    try:
        engine, agents = build_game(seed, cfg["players"], cfg["config_dir"], cfg["mode"], cfg["placeholder_fill"])
        winner = engine.run_game(agents, cfg["max_rounds"])
        game_id = f"seed{seed}"
        row = summarize_game(engine, winner, seed, agents, game_id)
        every = cfg["events_every"]
        if every and (seed - cfg["seed_start"]) % every == 0:
            write_events(engine.events, game_id, Path(cfg["out_dir"]) / "events" / f"{game_id}.parquet")
        return {"ok": True, "row": row}
    except MissingDataError as exc:
        return {"ok": False, "seed": seed, "error": str(exc)}


# ------------------------------------------------------------------ reporting
def wilson(wins: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    p = wins / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return centre - half, centre + half


def report(df: pd.DataFrame) -> str:
    n = len(df)
    done = df[df["winner_id"].notna()]
    lines = [f"games: {n}   finished: {len(done)}   timeouts: {n - len(done)}   mean rounds: {df['rounds'].mean():.1f}",
             f"end reasons: {df['end_reason'].value_counts().to_dict()}"]
    if len(done):
        lines.append("\nwin rate by ROLE (finished games, 95% Wilson CI):")
        for role in ("competitor", "monopolist"):
            w = int((done["winner_role"] == role).sum()); lo, hi = wilson(w, len(done))
            lines.append(f"  {role:<11} {w:>5}/{len(done)} = {w / len(done):6.1%}   [{lo:.1%}, {hi:.1%}]")
        appear: dict[str, int] = {}
        for agents_json in df["agents"]:
            for agent in json.loads(agents_json).values():
                appear[agent] = appear.get(agent, 0) + 1
        wins = done["winner_agent"].value_counts().to_dict()
        lines.append("\nwin rate by AGENT (wins / games the agent played in):")
        for agent, k in sorted(appear.items()):
            w = wins.get(agent, 0); lo, hi = wilson(w, k)
            lines.append(f"  {agent:<26} {w:>5}/{k} = {w / k:6.1%}   [{lo:.1%}, {hi:.1%}]")
    return "\n".join(lines)


# ------------------------------------------------------------------ run
def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def _git_commit() -> str | None:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True,
                              timeout=5).stdout.strip() or None
    except Exception:
        return None


def preflight(config_dir: str, placeholder_fill: bool, allow_incomplete: bool) -> bool:
    """Returns True if config is fully digitised and valid. Raises SystemExit on a refusal."""
    try:
        r = run_checks(config_dir)
    except yaml.YAMLError as exc:
        sys.exit(f"REFUSED: config unreadable: {exc}")
    if r.errors:
        sys.exit("REFUSED: config has errors - run `python -m tools.validate_config`:\n  " + "\n  ".join(r.errors[:10]))
    if r.pending and not (placeholder_fill or allow_incomplete):
        sys.exit(f"REFUSED: {len(r.pending)} fields are still null (cards/tiles not fully digitised), so results would be wrong.\n"
                 "Finish digitising (python -m tools.validate_config --list), or pass --placeholder-fill for a plumbing run,\n"
                 "or --allow-incomplete to run anyway and tag the manifest.")
    return not r.pending


def run(games: int, players: int, workers: int, out_dir: str, seed_start: int = 0, mode: str | None = None,
        max_rounds: int = 600, events_every: int = 0, placeholder_fill: bool = False,
        allow_incomplete: bool = False, config_dir: str = "config", quiet: bool = False) -> pd.DataFrame:
    complete = preflight(config_dir, placeholder_fill, allow_incomplete)
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    cfg = dict(players=players, config_dir=config_dir, mode=mode, placeholder_fill=placeholder_fill,
               max_rounds=max_rounds, events_every=events_every, seed_start=seed_start, out_dir=str(out))
    jobs = [(seed_start + i, cfg) for i in range(games)]
    t0 = time.time(); rows = []

    def consume(results):
        for res in results:
            if not res["ok"]:
                sys.exit(f"STOPPED at seed {res['seed']}: {res['error']}")     # abort: partial runs would be biased
            rows.append(res["row"])
            if not quiet and len(rows) % max(1, games // 10) == 0:
                print(f"  {len(rows)}/{games} games ({time.time() - t0:.1f}s)", flush=True)

    if workers <= 1:
        consume(play_one(j) for j in jobs)
    else:
        with Pool(workers) as pool:
            consume(pool.imap(play_one, jobs, chunksize=max(1, games // (workers * 8))))   # ordered -> seed order

    df = pd.DataFrame(rows)
    write_summaries(rows, out / "summary.parquet")
    manifest = dict(
        args=dict(games=games, players=players, workers=workers, seed_start=seed_start, mode=mode,
                  max_rounds=max_rounds, events_every=events_every),
        synthetic_placeholder_data=placeholder_fill, complete_data=complete,
        config_sha256={f: _sha(Path(config_dir, f)) for f in CONFIG_FILES},
        git_commit=_git_commit(), python=platform.python_version(), platform=platform.platform(),
        seconds=round(time.time() - t0, 2), pandas=pd.__version__,
    )
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2))
    if not quiet:
        if placeholder_fill:
            print(BANNER)
        elif not complete:
            print("*** INCOMPLETE DATA (--allow-incomplete): results are NOT valid for balance conclusions ***")
        print(report(df)); print(f"\nwrote {out}/summary.parquet and manifest.json  ({manifest['seconds']}s)")
    return df


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--games", type=int, default=1000)
    ap.add_argument("--players", type=int, default=4)
    ap.add_argument("--workers", type=int, default=1, help="processes; results do not depend on this")
    ap.add_argument("--seed-start", type=int, default=0)
    ap.add_argument("--mode", choices=["game_a", "game_b"], default=None)
    ap.add_argument("--max-rounds", type=int, default=600)
    ap.add_argument("--events-every", type=int, default=0, help="save full event log for every Nth game (0 = never)")
    ap.add_argument("--out-dir", default="out/monte_carlo")
    ap.add_argument("--placeholder-fill", action="store_true")
    ap.add_argument("--allow-incomplete", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args(argv)
    run(a.games, a.players, a.workers, a.out_dir, a.seed_start, a.mode, a.max_rounds, a.events_every,
        a.placeholder_fill, a.allow_incomplete, quiet=a.quiet)


if __name__ == "__main__":
    main()
