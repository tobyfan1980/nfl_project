"""Tests for results tracking (site_scripts/results.py)."""
import copy
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
