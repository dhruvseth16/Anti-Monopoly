"""Stage 3: telemetry round-trip, single-game runner, config validator."""
import copy
import json
from pathlib import Path

import pandas as pd
import yaml

from sim.game_factory import build_game
from sim.run_single_game import describe, run
from telemetry.event_log import COLUMNS, events_to_frame
from telemetry.run_logger import read_events, summarize_game, write_events
from tools.validate_config import Report, check_board, check_deck


def play(seed=1, mode=None, rounds=200):
    e, a = build_game(seed, 4, mode=mode, placeholder_fill=True)
    w = e.run_game(a, rounds)
    return e, a, w


# ---------------- telemetry ----------------
def test_frame_schema_and_payload_json():
    e, a, w = play()
    df = events_to_frame(e.events, "g1")
    assert list(df.columns) == COLUMNS and len(df) == len(e.events)
    assert df["seq"].tolist() == list(range(len(df)))
    assert df.iloc[0]["event_type"] == "game_start" and df.iloc[-1]["event_type"] == "game_end"
    json.loads(df.iloc[0]["payload"])                       # payload is valid JSON
    assert df[df.event_type == "buy"]["amount"].isna().all() # buy uses 'price' -> rides in payload, not 'amount'


def test_parquet_roundtrip(tmp_path):
    e, a, w = play(seed=5)
    p = write_events(e.events, "g5", tmp_path / "x" / "g5.parquet")
    back = read_events(p)
    pd.testing.assert_frame_equal(back, events_to_frame(e.events, "g5"))


def test_summary_row_matches_game():
    e, a, w = play(seed=2)
    s = summarize_game(e, w, 2, a, "g2")
    assert s["rounds"] == e.turn_count and s["n_events"] == len(e.events)
    assert (s["winner_id"] is None) == (w is None)
    if w: assert s["winner_role"] == w.role and s["end_reason"] in ("last_standing", "role_eliminated")


def test_every_logged_event_has_a_description_or_is_the_known_duplicate():
    e, a, w = play(seed=4)
    for ev in e.events:
        line = describe(ev, e.board)
        assert line is not None or ev["event"] == "rent_payment"


def test_game_b_ends_when_one_role_is_eliminated():
    ended = 0
    for s in range(30):
        e, a, w = play(seed=s, mode="game_b", rounds=400)
        end = e.events[-1]
        if end["reason"] == "role_eliminated":
            ended += 1
            alive = [p for p in e.players if not p.bankrupt]
            assert len({p.role for p in alive}) == 1 and w in alive
    assert ended > 0


def test_events_identical_for_same_seed():
    assert play(9)[0].events == play(9)[0].events


def test_single_game_cli_writes_files(tmp_path):
    out = tmp_path / "g.parquet"
    run(3, 4, 60, None, str(out), True, True)
    assert out.exists() and (tmp_path / "g_summary.parquet").exists()


# ---------------- validator ----------------
RULES = yaml.safe_load(Path("config/game_rules.yaml").read_text())
BOARD = yaml.safe_load(Path("config/board.yaml").read_text())


def validate(mutator):
    b = copy.deepcopy(BOARD); mutator(b); r = Report(); check_board(b, RULES, r); return r


def test_shipped_config_is_complete_and_valid():
    from tools.validate_config import run_checks
    r = run_checks("config")
    assert r.errors == [] and r.pending == [] and r.warnings == []


def test_validator_reports_pending_when_a_field_is_nulled():
    r = validate(lambda b: b[6]["rent"].update(competitor=None))
    assert any("rent.competitor" in m for m in r.pending)


def test_validator_catches_bad_rent_lists_and_group_size():
    r = validate(lambda b: b[1]["rent"]["competitor"].pop())
    assert any("6 rising" in m for m in r.errors)
    r = validate(lambda b: b[3].update(group_size=3))
    assert any("group_size" in m for m in r.errors)


def test_validator_catches_rule10_mismatch_and_bad_transport():
    r = validate(lambda b: b[1]["rent"]["monopolist"].__setitem__(0, 9))
    assert any("NO HOUSES" in m for m in r.errors)
    r = validate(lambda b: b[15].update(fare={"competitor": [20] * 4, "monopolist": [40, 80, 100, 320]}))
    assert any("double" in m for m in r.errors)


def test_deck_validation():
    r = Report()
    check_deck("d", [{"id": "comp_001", "text": "x", "effect": {"type": "teleport"}},
                     {"id": "comp_001", "text": "", "effect": {"type": "collect"}}], "comp_", r)
    joined = " | ".join(r.errors)
    assert "no handler" in joined and "duplicate" in joined and "text is empty" in joined and "needs 'amount'" in joined


def test_validator_rejects_duplicate_yaml_blocks_and_missing_rule_keys(tmp_path):
    import shutil, pytest
    from tools.validate_config import main
    for f in Path("config").glob("*.yaml"): shutil.copy(f, tmp_path / f.name)
    with open(tmp_path / "game_rules.yaml", "a") as fh:
        fh.write("\nbuilding:\n  monopolist:\n    monopolization_min_properties: 2\n")
    with pytest.raises(SystemExit) as exc: main(["--config-dir", str(tmp_path)])
    assert exc.value.code == 1
