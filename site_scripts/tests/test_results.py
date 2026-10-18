"""Tests for results tracking (site_scripts/results.py)."""
import copy
import json
import logging
from pathlib import Path

from accuracy import compute_accuracy
from results import update_results

FIX = Path(__file__).resolve().parent / "fixtures"
CSV = str(FIX / "games_sample.csv")
WEEK = str(FIX / "week_results_sample.json")


def test_update_results_marks_correct():
    out = update_results({}, 2026, 1, CSV, WEEK)

    # home-favored pick, home won (no '@') -> correct
    assert out["2026-W01-kc-den"] == {
        "season": 2026, "week": 1, "final": "27-20",
        "winner": "home", "picked": "home", "correct": True,
    }
    # home-favored pick, away won ('@' marker) -> incorrect; final is home-away
    assert out["2026-W01-chi-det"] == {
        "season": 2026, "week": 1, "final": "17-30",
        "winner": "away", "picked": "home", "correct": False,
    }
    # warming-up game: no prediction -> picked/correct null
    assert out["2026-W01-buf-mia"] == {
        "season": 2026, "week": 1, "final": "24-21",
        "winner": "home", "picked": None, "correct": None,
    }

    # the null-pick game is excluded from accuracy totals
    acc = compute_accuracy(out, 2026)
    assert acc["weeks"][0]["total"] == 2
    assert acc["weeks"][0]["correct"] == 1
    assert acc["overall"]["total"] == 2


def test_update_results_skips_unplayed_and_tied_games():
    out = update_results({}, 2026, 1, CSV, WEEK)
    assert "2026-W01-sf-sea" not in out  # not in CSV yet (unplayed)
    assert "2026-W01-dal-nyg" not in out  # tie: no home/away winner


def test_update_results_idempotent_and_preserves_other_weeks():
    other = {"2026-W02-x-y": {"season": 2026, "week": 2, "final": "1-0",
                              "winner": "home", "picked": "home", "correct": True}}
    once = update_results(copy.deepcopy(other), 2026, 1, CSV, WEEK)
    twice = update_results(copy.deepcopy(once), 2026, 1, CSV, WEEK)
    assert once == twice
    assert len(twice) == 4  # 3 week-1 games + 1 untouched week-2 game
    assert twice["2026-W02-x-y"] == other["2026-W02-x-y"]


def test_update_results_does_not_mutate_input():
    inp = {}
    update_results(inp, 2026, 1, CSV, WEEK)
    assert inp == {}


def test_update_results_ignores_other_weeks_in_csv():
    out = update_results({}, 2026, 2, CSV, WEEK)
    # week 2 CSV game (KC beat BUF) isn't in this week_json -> nothing added
    assert out == {}


def test_update_results_scores_neutral_site_game():
    # Neutral-site CSV row ("N" marker): Rams beat Jaguars 35-7. nflverse's
    # nominal home team (the week JSON) is the LOSER, so the CSV's own
    # home/away labelling can't be used; side must come from the week JSON.
    out = update_results({}, 2026, 3, CSV, str(FIX / "week_neutral_sample.json"))
    assert out["2026-W03-jax-lar"] == {
        "season": 2026, "week": 3, "final": "7-35",  # home(JAX)-away(LAR)
        "winner": "away", "picked": "home", "correct": False,
    }
    acc = compute_accuracy(out, 2026)
    assert acc["overall"] == {"correct": 0, "total": 1, "pct": 0.0, "record": "0-1"}


def test_update_results_side_follows_week_json_not_csv_marker(tmp_path):
    # Same normal game (CSV: KC home winner, no '@'), but the week JSON lists
    # the teams the other way round: winner must be reported as "away".
    wk = {"games": [{"id": "2026-W01-den-kc",
                     "home": {"team": "Denver Broncos"}, "away": {"team": "Kansas City Chiefs"},
                     "prediction": {"favored": "away"}}]}
    wk_path = tmp_path / "wk.json"
    wk_path.write_text(json.dumps(wk))
    out = update_results({}, 2026, 1, CSV, str(wk_path))
    assert out["2026-W01-den-kc"] == {
        "season": 2026, "week": 1, "final": "20-27",
        "winner": "away", "picked": "away", "correct": True,
    }


def test_update_results_warns_when_game_teams_not_in_csv(caplog, tmp_path):
    # A team spelled differently from the CSV (naming drift) must not vanish silently.
    wk = json.loads(Path(WEEK).read_text())
    wk["games"][0]["home"]["team"] = "Kansas City Chiefz"
    drift = tmp_path / "week_drift.json"
    drift.write_text(json.dumps(wk))
    gid = wk["games"][0]["id"]
    with caplog.at_level(logging.WARNING, logger="results"):
        out = update_results({}, 2026, 1, CSV, str(drift))
    assert gid not in out
    msgs = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert any(gid in m and "Kansas City Chiefz" in m and wk["games"][0]["away"]["team"] in m for m in msgs)
