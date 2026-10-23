"""Tests for accuracy tallies (site_scripts/accuracy.py)."""
import pytest

from accuracy import compute_accuracy


def _r(season, week, picked, correct):
    return {"season": season, "week": week, "final": "1-0",
            "winner": "home", "picked": picked, "correct": correct}


def _results():
    res = {}
    # week 6: 3 of 4 correct
    for i, c in enumerate([True, True, True, False]):
        res[f"2026-W06-a{i}-b{i}"] = _r(2026, 6, "home", c)
    # week 7: 1 of 2 correct, plus one warming-up (null) game excluded
    res["2026-W07-a0-b0"] = _r(2026, 7, "away", True)
    res["2026-W07-a1-b1"] = _r(2026, 7, "home", False)
    res["2026-W07-a2-b2"] = _r(2026, 7, None, None)
    # other season must be ignored
    res["2025-W06-a0-b0"] = _r(2025, 6, "home", False)
    return res


def test_compute_accuracy_totals():
    acc = compute_accuracy(_results(), 2026)
    assert acc["season"] == 2026
    w6, w7 = acc["weeks"]
    assert w6 == {"week": 6, "correct": 3, "total": 4, "pct": 0.75,
                  "cumulative_correct": 3, "cumulative_total": 4,
                  "cumulative_pct": 0.75}
    assert w7 == {"week": 7, "correct": 1, "total": 2, "pct": 0.5,
                  "cumulative_correct": 4, "cumulative_total": 6,
                  "cumulative_pct": 0.6667}
    assert acc["overall"] == {"correct": 4, "total": 6, "pct": 0.6667,
                              "record": "4-2"}

    # consistency invariant the history page relies on
    assert acc["overall"]["correct"] == sum(w["correct"] for w in acc["weeks"])
    assert acc["overall"]["total"] == sum(w["total"] for w in acc["weeks"])
    last = acc["weeks"][-1]
    assert acc["overall"]["correct"] == last["cumulative_correct"]
    assert acc["overall"]["total"] == last["cumulative_total"]
    assert acc["overall"]["pct"] == last["cumulative_pct"]


def test_compute_accuracy_excludes_null_and_empty_weeks():
    res = {"2026-W01-a-b": _r(2026, 1, None, None),
           "2026-W01-c-d": _r(2026, 1, None, None)}
    acc = compute_accuracy(res, 2026)
    assert acc["weeks"] == []  # warming-up-only week has no tally row
    assert acc["overall"] == {"correct": 0, "total": 0, "pct": 0.0,
                              "record": "0-0"}


def test_compute_accuracy_empty():
    acc = compute_accuracy({}, 2026)
    assert acc == {"season": 2026, "weeks": [],
                   "overall": {"correct": 0, "total": 0, "pct": 0.0,
                               "record": "0-0"}}


def test_compute_accuracy_weeks_sorted_and_rounded():
    res = {}
    for wk, flags in {9: [True, False, False], 3: [True]}.items():
        for i, c in enumerate(flags):
            res[f"2026-W{wk:02d}-a{i}-b{i}"] = _r(2026, wk, "home", c)
    acc = compute_accuracy(res, 2026)
    assert [w["week"] for w in acc["weeks"]] == [3, 9]
    assert acc["weeks"][1]["pct"] == pytest.approx(0.3333)
    assert acc["weeks"][1]["pct"] == round(1 / 3, 4)
    assert acc["overall"]["record"] == "2-2"
