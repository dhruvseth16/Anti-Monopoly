"""Audit the simulation in plain numbers so it can be compared with real tabletop play.

  python -m tools.sim_audit --games 300 --players 4 --max-rounds 600

Plays seeded games with the shipped agents and prints: speed, game length, timeouts, dice fairness,
where pawns land, how fast titles are bought, and what agents do with mortgages / houses / fines.
Seeds are deterministic, so the same arguments give the same numbers on any machine.
"""
from __future__ import annotations

import argparse
import collections
import statistics as st
import time

from sim.game_factory import build_game

EXPECTED_2D6 = {s: (6 - abs(s - 7)) / 36 for s in range(2, 13)}


def pct(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(p / 100 * len(xs)))] if xs else float("nan")


def audit(games: int, players: int, max_rounds: int, seed_start: int = 0) -> None:
    rounds_fin, rolls, events_n = [], [], []
    sums, doubles, total_rolls = collections.Counter(), 0, 0
    lands = collections.Counter()
    sold_out_round, owned_at = [], collections.defaultdict(list)
    first_bankrupt = []
    acts = collections.defaultdict(lambda: collections.Counter())      # role -> event -> count
    timeouts, timeout_states, winners = [], [], collections.Counter()
    t0 = time.perf_counter()

    for s in range(seed_start, seed_start + games):
        e, agents = build_game(s, players)
        role = {p.id: p.role for p in e.players}
        w = e.run_game(agents, max_rounds)
        events_n.append(len(e.events))
        r_count = 0
        buys_by_round = collections.Counter()
        for x in e.events:
            k, pid = x["event"], x["player_id"]
            if k == "roll":
                r_count += 1; total_rolls += 1
                d1, d2 = x["dice"]; sums[d1 + d2] += 1; doubles += d1 == d2
            elif k == "move":
                lands[x["to"]] += 1
            elif k == "buy":
                buys_by_round[x["turn"]] += 1; acts[role[pid]]["buy"] += 1
            elif k == "bankruptcy":
                acts[role[pid]]["bankruptcy"] += 1
            elif k == "sell_house":
                acts[role[pid]]["house sold (forced, half price)"] += 1
            elif k == "mortgage":
                acts[role[pid]]["mortgage (forced to pay a debt)"] += 1
            elif k in ("build", "unmortgage"):
                acts[role[pid]][k] += 1
            elif k == "jail_fine":
                acts[role[pid]]["jail fine paid"] += 1
            elif k == "leave_jail":
                acts[role[pid]][f"left jail via {x['how']}"] += 1
            elif k == "go_to_prison":
                acts[role[pid]]["sent to prison/price war"] += 1
        rolls.append(r_count)
        cum = 0
        for rd in range(1, 41):
            cum += buys_by_round.get(rd, 0)
            if rd in (3, 5, 10, 20, 40):
                owned_at[rd].append(cum)
        total = 0
        for rd in sorted(buys_by_round):
            total += buys_by_round[rd]
            if total >= 28:
                sold_out_round.append(rd); break
        fb = next((x["turn"] for x in e.events if x["event"] == "bankruptcy"), None)
        if fb: first_bankrupt.append(fb)
        if w is None:
            timeouts.append(s)
            alive = [p for p in e.players if not p.bankrupt]
            timeout_states.append((len(alive), "+".join(sorted(p.role[:4] for p in alive)),
                                   sum(p.cash for p in alive)))
        else:
            rounds_fin.append(e.turn_count); winners[w.role] += 1
    wall = time.perf_counter() - t0

    print(f"=== 1. SPEED  ({games} games, {players} players, max {max_rounds} rounds, one CPU core) ===")
    print(f"wall time {wall:.1f}s = {1000 * wall / games:.0f} ms/game; {total_rolls / games:,.0f} dice rolls/game "
          f"({total_rolls / wall:,.0f} rolls/s); {st.mean(events_n):,.0f} logged events/game")
    print("\n=== 2. GAME LENGTH (finished games) ===")
    if rounds_fin:
        print(f"rounds: mean {st.mean(rounds_fin):.0f}  median {st.median(rounds_fin):.0f}  p10 {pct(rounds_fin, 10)}  "
              f"p90 {pct(rounds_fin, 90)}  max {max(rounds_fin)}  min {min(rounds_fin)}")
        print(f"player-turns (dice rolls) per game: mean {st.mean(rolls):.0f} median {st.median(rolls):.0f}")
        for sec in (20, 30, 45, 60):
            print(f"  at {sec:>2}s per physical turn -> mean {st.mean(rolls) * sec / 3600:.1f} h, "
                  f"median {st.median(rolls) * sec / 3600:.1f} h")
    print(f"timeouts (no winner after {max_rounds} rounds): {len(timeouts)}/{games} = {len(timeouts) / games:.1%}")
    if timeout_states:
        c = collections.Counter((a, r) for a, r, _ in timeout_states)
        print(f"  players still alive at timeout: {dict(c)};  mean total cash of survivors ${st.mean(x[2] for x in timeout_states):,.0f}")
    print("\n=== 3. DICE ===")
    print(f"{total_rolls:,} rolls. doubles: {doubles / total_rolls:.2%} (fair = 16.67%)")
    chi = 0.0
    print("sum  observed  expected")
    for sm in range(2, 13):
        o, ex = sums[sm] / total_rolls, EXPECTED_2D6[sm]
        chi += (sums[sm] - ex * total_rolls) ** 2 / (ex * total_rolls)
        print(f"{sm:>3}  {o:7.2%}  {ex:7.2%}")
    print(f"chi-square {chi:.1f} with 10 d.o.f. (fair dice stay below 18.3 about 95% of the time)")
    print("\n=== 4. WHERE PAWNS LAND (share of all landings; uniform would be 2.50%) ===")
    n_land = sum(lands.values())
    top = lands.most_common(5); low = lands.most_common()[-3:]
    print("most:  " + ", ".join(f"tile {t} {c / n_land:.1%}" for t, c in top))
    print("least: " + ", ".join(f"tile {t} {c / n_land:.1%}" for t, c in low))
    print("\n=== 5. TEMPO ===")
    print("titles owned after round: " + ", ".join(f"{rd}: {st.mean(v):.1f}/28" for rd, v in sorted(owned_at.items())))
    if sold_out_round: print(f"all 28 titles sold by round: median {st.median(sold_out_round):.0f} (in {len(sold_out_round)}/{games} games)")
    if first_bankrupt: print(f"first bankruptcy: median round {st.median(first_bankrupt):.0f}  p10 {pct(first_bankrupt, 10)}  p90 {pct(first_bankrupt, 90)}")
    print("\n=== 6. WHAT PLAYERS DO (average per game, summed over all players of that role) ===")
    names = sorted({k for r in acts.values() for k in r})
    print(f"{'action':<38}{'competitors':>12}{'monopolists':>13}")
    for k in names:
        print(f"{k:<38}{acts['competitor'][k] / games:>12.1f}{acts['monopolist'][k] / games:>13.1f}")
    print(f"\nwinners: {dict(winners)}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--games", type=int, default=300)
    ap.add_argument("--players", type=int, default=4)
    ap.add_argument("--max-rounds", type=int, default=600)
    ap.add_argument("--seed-start", type=int, default=0)
    a = ap.parse_args(argv)
    audit(a.games, a.players, a.max_rounds, a.seed_start)


if __name__ == "__main__":
    main()
