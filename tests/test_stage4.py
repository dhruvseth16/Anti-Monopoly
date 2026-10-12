"""Stage 4: Monte Carlo driver - reproducibility, refusal on incomplete data, outputs."""
import json

import pandas as pd
import pytest

from sim.run_monte_carlo import report, run, wilson


def mc(tmp_path, name, **kw):
    args = dict(games=24, players=4, workers=1, out_dir=str(tmp_path / name), max_rounds=200,
                placeholder_fill=True, quiet=True)
    args.update(kw)
    return run(**args)


def test_results_identical_for_any_worker_count(tmp_path):
    a = mc(tmp_path, "w1", workers=1)
    b = mc(tmp_path, "w2", workers=2)
    pd.testing.assert_frame_equal(a, b)                      # same seeds -> same rows, same order


def test_rerun_is_identical_and_seed_range_is_respected(tmp_path):
    a = mc(tmp_path, "a", seed_start=100, games=10)
    b = mc(tmp_path, "b", seed_start=100, games=10)
    pd.testing.assert_frame_equal(a, b)
    assert a["seed"].tolist() == list(range(100, 110))


def test_outputs_manifest_and_event_sampling(tmp_path):
    df = mc(tmp_path, "o", games=12, events_every=5)
    out = tmp_path / "o"
    assert (out / "summary.parquet").exists()
    m = json.loads((out / "manifest.json").read_text())
    assert m["synthetic_placeholder_data"] is True and m["complete_data"] is True
    assert set(m["config_sha256"]) >= {"board.yaml", "game_rules.yaml"} and m["args"]["games"] == 12
    assert sorted(p.name for p in (out / "events").glob("*.parquet")) == ["seed0.parquet", "seed10.parquet", "seed5.parquet"]
    assert len(pd.read_parquet(out / "summary.parquet")) == len(df) == 12


def test_real_run_refused_while_config_has_null_fields(tmp_path):
    import shutil
    import yaml
    cfg = tmp_path / "cfg"; shutil.copytree("config", cfg)
    board = yaml.safe_load((cfg / "board.yaml").read_text())
    board[6]["house_cost"] = None
    (cfg / "board.yaml").write_text(yaml.safe_dump(board, sort_keys=False))
    with pytest.raises(SystemExit) as exc:
        mc(tmp_path, "nope", placeholder_fill=False, config_dir=str(cfg))
    assert "REFUSED" in str(exc.value) and "null" in str(exc.value)


def test_real_data_runs_without_any_flag(tmp_path):
    df = mc(tmp_path, "real", placeholder_fill=False, games=10)
    assert len(df) == 10 and json.loads((tmp_path / "real" / "manifest.json").read_text())["complete_data"] is True


def test_game_b_mode_runs(tmp_path):
    df = mc(tmp_path, "b", mode="game_b", games=15)
    assert (df["mode"] == "game_b").all()
    assert set(df["end_reason"]) <= {"last_standing", "role_eliminated", "timeout"}


def test_report_and_wilson():
    lo, hi = wilson(50, 100)
    assert 0.40 < lo < 0.41 and 0.59 < hi < 0.60
    text = report(mc.__globals__["pd"].DataFrame({
        "winner_id": [0, 1, None], "winner_role": ["competitor", "monopolist", None], "rounds": [10, 20, 600],
        "end_reason": ["last_standing", "last_standing", "timeout"],
        "agents": [json.dumps({"0": "a", "1": "b"})] * 3, "winner_agent": ["a", "b", None]}))
    assert "competitor" in text and "timeouts: 1" in text
