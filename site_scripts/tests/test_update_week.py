"""Tests for the weekly orchestration (site_scripts/update_week.py).

No network, crawl or real site/data: every fetcher/pipeline function is
monkeypatched and all output goes to a pytest tmp dir.
"""
import csv
import json
from pathlib import Path

import pytest

import update_week
from predict import predict_home_win

HEADER = ["Week", "Day", "Date", "Time", "Winner/tie", "", "Loser/tie", "Date",
          "PtsW", "PtsL", "YdsW", "TOW", "YdsL", "TOL", "zipcode", "temperature",
          "condition"]

KC, DEN, LV, BUF = ("Kansas City Chiefs", "Denver Broncos", "Las Vegas Raiders",
                    "Buffalo Bills")


def _row(week, date, winner, loser, ptsw, ptsl, marker=""):
    return [str(week), "Sun", date, "1:00PM", winner, marker, loser, date,
            str(ptsw), str(ptsl), "", "", "", "", "", "", ""]


# KC: W1 W(home) W2 W(home) W3 L(away, at LV) W4 W(home) W5 W(away) W6 W(home)
# -> 5-1, streak W3. A Week 7 row exists (a re-run after the game was played)
# and must NOT count towards the "as of week 7" record.
GAMES = [
    _row(1, "2026-09-13", KC, DEN, 27, 20),
    _row(2, "2026-09-20", KC, BUF, 10, 9),
    _row(3, "2026-09-27", LV, KC, 20, 17),
    _row(4, "2026-10-04", KC, "New York Giants", 30, 10),
    _row(5, "2026-10-11", KC, BUF, 24, 21, marker="@"),
    _row(6, "2026-10-18", KC, DEN, 27, 20),
    _row(7, "2026-10-25", KC, DEN, 31, 3),
]

SCHEDULE = [
    {"id": "2026-W07-kc-den", "kickoff_utc": "2026-10-25T20:25:00Z",
     "home_team": KC, "home_slug": "kc", "away_team": DEN, "away_slug": "den"},
    {"id": "2026-W07-lv-buf", "kickoff_utc": "2026-10-25T17:00:00Z",
     "home_team": LV, "home_slug": "lv", "away_team": BUF, "away_slug": "buf"},
]

LAST5 = {KC: 0.8, DEN: 0.4, LV: None, BUF: 0.6}  # None -> warming up

ODDS = {"2026-W07-kc-den": {
    "home_moneyline": -340, "away_moneyline": 270, "books": 9,
    "source": "the-odds-api", "pulled_at": "2026-10-20T10:11:50Z"}}

INJURIES = {"available": False, "pulled_at": "2026-10-20T10:12:30Z",
            "reason": "robots.txt disallows fetch", "teams": {}}


@pytest.fixture
def env(tmp_path, monkeypatch):
    data = tmp_path / "data"
    data.mkdir()
    (data / "season.json").write_text(json.dumps(
        {"season": 2026, "current_week": 6, "model_active_from_week": 6}))
    (data / "results.json").write_text("{}")
    # Previous week's published page: one pick, so there is a result to score.
    (data / "week_06.json").write_text(json.dumps({
        "season": 2026, "week": 6, "generated_at": "2026-10-13T10:00:00Z",
        "games": [{"id": "2026-W06-kc-den",
                   "home": {"team": KC, "slug": "kc"},
                   "away": {"team": DEN, "slug": "den"},
                   "prediction": {"home_win_prob": 0.74, "away_win_prob": 0.26,
                                  "favored": "home"}}]}))
    games_csv = tmp_path / "2026_games.csv"
    with games_csv.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(HEADER)
        w.writerows(GAMES)

    calls = []
    monkeypatch.setattr(update_week, "games_csv_path", lambda season: games_csv)
    monkeypatch.setattr(update_week, "ingest_week",
                        lambda season, week: calls.append(("ingest", season, week)))
    monkeypatch.setattr(update_week, "regenerate_metrics",
                        lambda season: calls.append(("metrics", season)))
    monkeypatch.setattr(update_week, "fetch_schedule",
                        lambda season, week, **kw: [dict(g) for g in SCHEDULE])
    monkeypatch.setattr(update_week, "fetch_odds", lambda games: dict(ODDS))
    monkeypatch.setattr(update_week, "fetch_injury_report", lambda season, week: dict(INJURIES))
    monkeypatch.setattr(update_week, "current_last5",
                        lambda season, team, before: LAST5[team])
    return data, calls


def _load(data, name):
    return json.loads((data / name).read_text())


def _games_by_id(data):
    return {g["id"]: g for g in _load(data, "week_07.json")["games"]}


def test_update_week_writes_site_data(env):
    data, _ = env
    update_week.main(["--season", "2026", "--week", "7", "--data-dir", str(data),
                      "--skip-ingest"])

    week = _load(data, "week_07.json")
    assert (week["season"], week["week"]) == (2026, 7)
    games = _games_by_id(data)
    assert set(games) == {"2026-W07-kc-den", "2026-W07-lv-buf"}

    # Both last-5 rates present -> prediction built from the real predictor.
    kc = games["2026-W07-kc-den"]
    expected = predict_home_win(0.8, 0.4)
    assert kc["prediction"] == {
        "home_win_prob": expected["home_win_prob"],
        "away_win_prob": expected["away_win_prob"],
        "favored": "home",
        "home_last5_win_rate": 0.8,
        "away_last5_win_rate": 0.4,
        "diff": pytest.approx(0.4),
        "model": expected["model"],
    }
    assert kc["odds"] == ODDS["2026-W07-kc-den"]
    assert kc["kickoff_utc"] == "2026-10-25T20:25:00Z"

    # One side warming up (current_last5 None) -> null prediction, no odds.
    lv = games["2026-W07-lv-buf"]
    assert lv["prediction"] is None
    assert lv["odds"] is None

    assert _load(data, "season.json") == {
        "season": 2026, "current_week": 7, "model_active_from_week": 6}
    assert _load(data, "injuries.json") == INJURIES

    # Previous week scored into results.json; accuracy is self-consistent.
    results = _load(data, "results.json")
    assert results["2026-W06-kc-den"] == {
        "season": 2026, "week": 6, "final": "27-20",
        "winner": "home", "picked": "home", "correct": True}
    acc = _load(data, "accuracy.json")
    assert acc["season"] == 2026
    assert acc["overall"]["total"] == sum(w["total"] for w in acc["weeks"]) == 1
    assert acc["overall"]["correct"] == sum(w["correct"] for w in acc["weeks"]) == 1
    assert acc["overall"]["record"] == "1-0"


def test_record_streak_and_last5_derived_from_games_csv(env):
    data, _ = env
    update_week.main(["--season", "2026", "--week", "7", "--data-dir", str(data),
                      "--skip-ingest"])
    kc = _games_by_id(data)["2026-W07-kc-den"]
    # Only weeks < 7 count (the Week 7 row in the CSV is ignored).
    assert kc["home"] == {"team": KC, "slug": "kc", "record": "5-1", "streak": "W3"}
    assert kc["away"] == {"team": DEN, "slug": "den", "record": "0-2", "streak": "L2"}
    assert kc["last5_home"] == [
        {"opponent": "den", "result": "W", "score": "27-20", "home_away": "home"},
        {"opponent": "buf", "result": "W", "score": "24-21", "home_away": "away"},
        {"opponent": "nyg", "result": "W", "score": "30-10", "home_away": "home"},
        {"opponent": "lv", "result": "L", "score": "17-20", "home_away": "away"},
        {"opponent": "buf", "result": "W", "score": "10-9", "home_away": "home"},
    ]
    assert kc["last5_away"][0] == {
        "opponent": "kc", "result": "L", "score": "20-27", "home_away": "away"}


def test_team_with_no_games_gets_contract_valid_defaults(env):
    data, _ = env
    update_week.main(["--season", "2026", "--week", "7", "--data-dir", str(data),
                      "--skip-ingest"])
    buf = _games_by_id(data)["2026-W07-lv-buf"]["away"]
    # BUF has games (2 losses) - sanity; a brand-new team is covered below.
    assert buf["record"] == "0-2"
    rec, streak = update_week.team_record_and_streak([])
    assert (rec, streak) == ("0-0", "W0")


def test_predictions_use_current_last5_by_full_name_before_kickoff_date(env, monkeypatch):
    data, _ = env
    seen = []

    def fake(season, team, before):
        seen.append((season, team, before))
        return LAST5[team]

    monkeypatch.setattr(update_week, "current_last5", fake)
    update_week.main(["--season", "2026", "--week", "7", "--data-dir", str(data),
                      "--skip-ingest"])
    assert (2026, KC, "2026-10-25") in seen
    assert (2026, DEN, "2026-10-25") in seen


def test_default_model_active_from_week_is_6():
    assert update_week.DEFAULT_MODEL_ACTIVE_FROM_WEEK == 6


def test_week_gate_nulls_prediction_below_active_week_even_with_games(monkeypatch):
    # current_last5 would happily return a rate; the week gate must still win.
    monkeypatch.setattr(update_week, "current_last5",
                        lambda season, team, before: 0.6 if team == KC else 0.4)
    game = dict(SCHEDULE[0])
    for week in (1, 2, 3, 4, 5):
        assert update_week._prediction(2026, game, week) is None
    pred = update_week._prediction(2026, game, 6)
    assert pred is not None
    assert pred["home_last5_win_rate"] == 0.6 and pred["away_last5_win_rate"] == 0.4
    assert update_week._prediction(2026, game, 7) is not None
    # an explicit (maintainer) active_from is honoured
    assert update_week._prediction(2026, game, 3, active_from=3) is not None
    assert update_week._prediction(2026, game, 2, active_from=3) is None


def test_week_3_page_has_null_predictions_but_still_lists_games(env, monkeypatch):
    data, _ = env
    monkeypatch.setattr(update_week, "current_last5",
                        lambda season, team, before: 0.5)
    update_week.main(["--season", "2026", "--week", "3", "--data-dir", str(data),
                      "--skip-ingest"])
    games = _load(data, "week_03.json")["games"]
    assert len(games) == len(SCHEDULE)
    assert all(g["prediction"] is None for g in games)
    assert _load(data, "season.json")["model_active_from_week"] == 6


def test_week_6_page_is_predicted(env, monkeypatch):
    data, _ = env
    monkeypatch.setattr(update_week, "current_last5",
                        lambda season, team, before: 0.5)
    update_week.main(["--season", "2026", "--week", "6", "--data-dir", str(data),
                      "--skip-ingest"])
    games = _load(data, "week_06.json")["games"]
    assert all(g["prediction"] is not None for g in games)


def test_local_game_date_handles_evening_kickoffs_that_are_next_day_in_utc():
    # Sunday-night / Monday-night / Thursday-night kickoffs roll over in UTC.
    assert update_week._local_game_date("2026-09-14T00:20:00Z") == "2026-09-13"
    assert update_week._local_game_date("2026-09-11T00:35:00Z") == "2026-09-10"
    assert update_week._local_game_date("2026-12-07T01:15:00Z") == "2026-12-06"
    assert update_week._local_game_date("2026-10-25T17:00:00Z") == "2026-10-25"
    assert update_week._local_game_date("2026-10-04T13:30:00Z") == "2026-10-04"


def test_orchestration_order_and_skip_ingest(env, monkeypatch):
    data, calls = env
    update_week.main(["--season", "2026", "--week", "7", "--data-dir", str(data)])
    # Ingest is for LAST week's games, then metrics regenerate.
    assert calls == [("ingest", 2026, 6), ("metrics", 2026)]

    calls.clear()
    update_week.main(["--season", "2026", "--week", "7", "--data-dir", str(data),
                      "--skip-ingest"])
    assert calls == [("metrics", 2026)]


def test_idempotent_per_season_week(env):
    data, _ = env
    argv = ["--season", "2026", "--week", "7", "--data-dir", str(data),
            "--skip-ingest"]
    update_week.main(argv)

    def snapshot():
        out = {}
        for name in ("week_07.json", "results.json", "accuracy.json",
                     "season.json", "injuries.json"):
            body = _load(data, name)
            if name == "week_07.json":
                body.pop("generated_at")
            out[name] = body
        return out

    first = snapshot()
    update_week.main(argv)
    assert snapshot() == first


def test_no_previous_week_page_is_skipped_gracefully(env):
    data, _ = env
    (data / "week_06.json").unlink()
    update_week.main(["--season", "2026", "--week", "7", "--data-dir", str(data),
                      "--skip-ingest"])
    assert _load(data, "results.json") == {}
    assert _load(data, "accuracy.json")["overall"]["total"] == 0
    assert (data / "week_07.json").exists()


def test_summary_reminds_to_push(env, capsys):
    data, _ = env
    update_week.main(["--season", "2026", "--week", "7", "--data-dir", str(data),
                      "--skip-ingest"])
    out = capsys.readouterr().out
    assert "week_07.json" in out
    assert "git add site/data && git commit && git push" in out


def test_generated_week_file_satisfies_data_contract(env):
    from test_data_contract import (check_keys, check_odds, check_prediction,
                                    check_result, check_team)
    data, _ = env
    update_week.main(["--season", "2026", "--week", "7", "--data-dir", str(data),
                      "--skip-ingest"])
    week = _load(data, "week_07.json")
    check_keys(week, {"season", "week", "generated_at", "games"}, "week_07.json")
    for g in week["games"]:
        check_keys(g, {"id", "kickoff_utc", "home", "away", "prediction", "odds",
                       "last5_home", "last5_away"}, g["id"])
        check_team(g["home"], "home")
        check_team(g["away"], "away")
        assert g["id"] == f"2026-W07-{g['home']['slug']}-{g['away']['slug']}"
        if g["prediction"]:
            check_prediction(g["prediction"], "prediction")
        if g["odds"]:
            check_odds(g["odds"], "odds")
        for key in ("last5_home", "last5_away"):
            for r in g[key]:
                check_result(r, key)


def test_missing_games_csv_logs_warning(env, monkeypatch, caplog):
    data, _ = env
    monkeypatch.setattr(update_week, "games_csv_path",
                        lambda season: data / "nope_games.csv")
    with caplog.at_level("WARNING", logger="update_week"):
        update_week.main(["--season", "2026", "--week", "7", "--data-dir",
                          str(data), "--skip-ingest"])
    assert any("games CSV" in r.message and "missing" in r.message
               for r in caplog.records)
    assert _games_by_id(data)["2026-W07-kc-den"]["home"]["record"] == "0-0"
