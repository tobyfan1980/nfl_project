"""Tests for the data-pipeline wrappers (site_scripts/pipeline.py).

No real crawl or network: subprocess.run is monkeypatched everywhere.
"""
import csv
import sys
from pathlib import Path

import pytest

import pipeline

FIX = Path(__file__).resolve().parent / "fixtures"

HEADER = ["Week", "Day", "Date", "Time", "Winner/tie", "", "Loser/tie", "Date",
          "PtsW", "PtsL", "YdsW", "TOW", "YdsL", "TOL", "zipcode", "temperature",
          "condition"]
CRAWLER_HEADER = ["Date", "Home Team", "Away Team", "Home Score", "Away Score",
                  "Home Rushing Yards", "Away Rushing Yards",
                  "Home Passing Yards", "Away Passing Yards"]


def _write(path, header, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def _read(path):
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.reader(f))


# --------------------------------------------------------------- current_last5

def _last5_repo(tmp_path, monkeypatch):
    """Games CSV fixture: KC has 6 finished games, DEN 4, week-7 game not played."""
    def row(week, date, winner, loser, pw, pl, marker=""):
        return [str(week), "Sun", date, "1:00PM", winner, marker, loser, date,
                str(pw), str(pl), "", "", "", "", "", "", ""]
    KC, DEN, BUF = "Kansas City Chiefs", "Denver Broncos", "Buffalo Bills"
    rows = [
        row(1, "2026-09-13", KC, DEN, 27, 20),    # KC W
        row(2, "2026-09-20", KC, BUF, 10, 9),     # KC W
        row(3, "2026-09-27", BUF, KC, 20, 17),    # KC L
        row(4, "2026-10-04", KC, DEN, 17, 17),    # KC T (and DEN T)
        row(5, "2026-10-11", KC, BUF, 24, 21),    # KC W
        row(6, "2026-10-18", DEN, KC, 30, 10, "@"),  # KC L (away win by DEN)
    ]
    _write(tmp_path / "dev_data" / "games" / "2026_games.csv", HEADER, rows)
    monkeypatch.setattr(pipeline, "REPO_ROOT", tmp_path)


def test_current_last5_computed_from_games_csv(tmp_path, monkeypatch):
    _last5_repo(tmp_path, monkeypatch)
    kc = "Kansas City Chiefs"
    # 5 most recent KC games before 10-25: W2 W, W3 L, W4 T, W5 W, W6 L
    # -> (2 wins + 0.5 tie) / 5; the most recent game (W6, 10-18) IS included.
    assert pipeline.current_last5(2026, kc, "2026-10-25") == 0.5
    # Without W6 (before 10-18) the window is W1..W5: W, W, L, T, W -> 3.5/5
    assert pipeline.current_last5(2026, kc, "2026-10-18") == 0.7
    # A game dated ON before_date is not "before": only 4 games -> warming up
    assert pipeline.current_last5(2026, kc, "2026-10-11") is None
    # Window slides to the 5 most recent (not the first 5) as games accrue
    assert pipeline.current_last5(2026, kc, "2026-12-01") == 0.5
    # Team with fewer than 5 completed games -> None (warming up)
    assert pipeline.current_last5(2026, "Denver Broncos", "2026-12-01") is None
    assert pipeline.current_last5(2026, "Buffalo Bills", "2026-12-01") is None
    # Unknown team / no games file for the season -> None
    assert pipeline.current_last5(2026, "Nowhere Nobodies", "2026-12-01") is None
    assert pipeline.current_last5(2031, kc, "2031-12-01") is None


# ------------------------------------------------- subprocess invocation (mocked)

def _fake_repo(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(pipeline, "METRICS_DIR", tmp_path / "dev_data" / "metrics")
    return tmp_path


def test_ingest_and_regenerate_invoke_scripts(tmp_path, monkeypatch):
    root = _fake_repo(tmp_path, monkeypatch)
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append((list(cmd), kwargs))
        if "nfl_crawler.py" in cmd[1]:
            _write(root / "dev_data" / "games" / "nfl_2026_week_3_game_stats.csv",
                   CRAWLER_HEADER,
                   [["2026-09-20", "Denver Broncos", "Kansas City Chiefs",
                     "20", "27", "100", "120", "200", "230"]])
        return None

    monkeypatch.setattr(pipeline.subprocess, "run", fake_run)

    pipeline.ingest_week(2026, 3)
    assert len(calls) == 1
    cmd, kw = calls[0]
    assert cmd[0] == sys.executable
    assert cmd[1] == str(root / "tools" / "nfl_crawler.py")
    assert cmd[2:] == ["--year", "2026", "--week", "3"]
    assert kw["check"] is True
    assert kw["cwd"] == str(root)  # crawler writes cwd-relative output paths
    assert (root / "dev_data" / "games" / "2026_games.csv").exists()

    calls.clear()
    pipeline.regenerate_metrics(2026)
    scripts = [Path(c[1]).name for c, _ in calls]
    assert scripts == ["generate_season_win_rates.py",
                       "generate_season_opponent_strength.py",
                       "generate_season_game_intervals.py",
                       "generate_season_travel.py"]
    for cmd, kw in calls:
        assert cmd[0] == sys.executable
        assert Path(cmd[1]).parent.parent.parent == root / "plugins"
        assert Path(cmd[1]).parent.name == "scripts"
        assert "--overwrite" in cmd
        assert cmd[cmd.index("--years") + 1] == "2026"
        assert cmd[cmd.index("--input-dir") + 1] == str(root / "dev_data" / "games")
        assert cmd[cmd.index("--output-dir") + 1] == str(root / "dev_data" / "metrics")
        assert kw["check"] is True
        assert kw["cwd"] == str(root)
    travel_cmd = calls[3][0]
    assert travel_cmd[travel_cmd.index("--team-zipcodes") + 1] == str(
        root / "dev_data" / "reference" / "nfl_teams_stadium_zip_only_5digit_text.csv")


def test_ingest_week_raises_when_crawler_produces_nothing(tmp_path, monkeypatch):
    _fake_repo(tmp_path, monkeypatch)
    # crawler exits 0 but writes no file (it prints "No game data" and returns)
    monkeypatch.setattr(pipeline.subprocess, "run", lambda cmd, **kw: None)
    with pytest.raises(RuntimeError):
        pipeline.ingest_week(2026, 3)


def test_ingest_crawler_failure_propagates(tmp_path, monkeypatch):
    _fake_repo(tmp_path, monkeypatch)

    def boom(cmd, **kw):
        raise pipeline.subprocess.CalledProcessError(1, cmd)

    monkeypatch.setattr(pipeline.subprocess, "run", boom)
    with pytest.raises(pipeline.subprocess.CalledProcessError):
        pipeline.ingest_week(2026, 3)


def test_regenerate_best_effort_generator_failure_continues(tmp_path, monkeypatch, caplog):
    _fake_repo(tmp_path, monkeypatch)
    attempted = []

    def fake_run(cmd, **kw):
        name = Path(cmd[1]).name
        attempted.append(name)
        if name == "generate_season_opponent_strength.py":  # non-win_rate fails
            raise pipeline.subprocess.CalledProcessError(1, cmd)

    monkeypatch.setattr(pipeline.subprocess, "run", fake_run)
    pipeline.regenerate_metrics(2026)  # must return normally
    assert attempted == ["generate_season_win_rates.py",
                         "generate_season_opponent_strength.py",
                         "generate_season_game_intervals.py",
                         "generate_season_travel.py"]
    assert "generate_season_opponent_strength.py" in caplog.text


def test_regenerate_travel_failure_does_not_block_win_rate(tmp_path, monkeypatch):
    _fake_repo(tmp_path, monkeypatch)
    attempted = []

    def fake_run(cmd, **kw):
        name = Path(cmd[1]).name
        attempted.append(name)
        if name == "generate_season_travel.py":
            raise pipeline.subprocess.CalledProcessError(1, cmd)

    monkeypatch.setattr(pipeline.subprocess, "run", fake_run)
    pipeline.regenerate_metrics(2026)
    assert attempted[0] == "generate_season_win_rates.py"
    assert attempted[-1] == "generate_season_travel.py"


def test_regenerate_win_rate_failure_propagates(tmp_path, monkeypatch):
    _fake_repo(tmp_path, monkeypatch)
    attempted = []

    def fake_run(cmd, **kw):
        attempted.append(Path(cmd[1]).name)
        if Path(cmd[1]).name == "generate_season_win_rates.py":
            raise pipeline.subprocess.CalledProcessError(1, cmd)

    monkeypatch.setattr(pipeline.subprocess, "run", fake_run)
    with pytest.raises(pipeline.subprocess.CalledProcessError):
        pipeline.regenerate_metrics(2026)
    assert attempted == ["generate_season_win_rates.py"]


# ------------------------------------------------------------------ merge helper

ZIPS = {"Denver Broncos": "80204", "Kansas City Chiefs": "64129"}


def test_convert_crawler_rows_to_season_format():
    rows = pipeline.convert_crawler_rows(
        [{"Date": "2026-09-20", "Home Team": "Denver Broncos",
          "Away Team": "Kansas City Chiefs", "Home Score": "20", "Away Score": "27",
          "Home Rushing Yards": "100", "Away Rushing Yards": "120",
          "Home Passing Yards": "200", "Away Passing Yards": "230"},
         {"Date": "2026-09-21", "Home Team": "Denver Broncos",
          "Away Team": "Kansas City Chiefs", "Home Score": "31", "Away Score": "10",
          "Home Rushing Yards": "", "Away Rushing Yards": "",
          "Home Passing Yards": "", "Away Passing Yards": ""}],
        week=3, zipcodes=ZIPS)
    away_win, home_win = rows
    # away team won -> '@' marker, winner = away; yards = rush + pass of winner
    assert away_win == ["3", "Sun", "2026-09-20", "", "Kansas City Chiefs", "@",
                        "Denver Broncos", "2026-09-20", "27", "20", "350", "",
                        "300", "", "80204", "", ""]
    # home team won -> no marker; missing yardage left blank
    assert home_win[4:10] == ["Denver Broncos", "", "Kansas City Chiefs",
                              "2026-09-21", "31", "10"]
    assert home_win[10] == "" and home_win[12] == ""
    assert len(away_win) == len(HEADER)


def test_merge_replaces_week_and_dedupes(tmp_path):
    games = tmp_path / "2026_games.csv"

    def row(week, date, w, mark, l, pw="27", pl="20"):
        return [str(week), "Sun", date, "", w, mark, l, date, pw, pl,
                "", "", "", "", "", "", ""]

    _write(games, HEADER, [
        row(1, "2026-09-06", "Buffalo Bills", "", "Miami Dolphins"),
        row(3, "2026-09-20", "Kansas City Chiefs", "@", "Denver Broncos", "1", "0"),
        row(3, "2026-09-20", "Green Bay Packers", "", "Chicago Bears"),
    ])
    new = [
        # same teams+date as an existing week-3 row, new score: replaces it
        row(3, "2026-09-20", "Kansas City Chiefs", "@", "Denver Broncos", "27", "20"),
        # exact duplicate within the incoming batch: kept once
        row(3, "2026-09-20", "Kansas City Chiefs", "@", "Denver Broncos", "27", "20"),
        row(3, "2026-09-21", "Detroit Lions", "", "Minnesota Vikings"),
    ]
    pipeline.merge_week_rows(games, new, week=3)
    out = _read(games)
    assert out[0] == HEADER
    body = out[1:]
    # week 1 untouched; old week-3 rows gone (Packers row replaced because the
    # whole week is replaced); new rows present exactly once
    assert [(r[0], r[4]) for r in body] == [
        ("1", "Buffalo Bills"),
        ("3", "Kansas City Chiefs"),
        ("3", "Detroit Lions"),
    ]
    assert body[1][8] == "27"


def test_merge_week_match_is_numeric_and_write_is_atomic(tmp_path, monkeypatch):
    games = tmp_path / "2026_games.csv"

    def row(week, date, w, l, pw="27"):
        return [week, "Sun", date, "", w, "", l, date, pw, "20",
                "", "", "", "", "", "", ""]

    _write(games, HEADER, [
        row("03", "2026-09-20", "Kansas City Chiefs", "Denver Broncos", "1"),
        row("3.0", "2026-09-20", "Green Bay Packers", "Chicago Bears"),
        row("wild-card", "2027-01-10", "Buffalo Bills", "Miami Dolphins"),
    ])
    replaced = []
    real_replace = pipeline.os.replace
    monkeypatch.setattr(pipeline.os, "replace",
                        lambda a, b: (replaced.append((a, b)), real_replace(a, b))[1])
    pipeline.merge_week_rows(
        games, [row("3", "2026-09-20", "Kansas City Chiefs", "Denver Broncos")], week=3)
    body = _read(games)[1:]
    # "03" and "3.0" week-3 rows replaced; non-numeric playoff row kept
    assert [(r[0], r[4]) for r in body] == [
        ("3", "Kansas City Chiefs"), ("wild-card", "Buffalo Bills")]
    # written via temp file + os.replace, no temp file left behind
    assert replaced and replaced[0][1] == games
    assert list(tmp_path.glob("*.tmp")) == []


def test_merge_creates_file_when_missing(tmp_path):
    games = tmp_path / "games" / "2026_games.csv"
    r = ["1", "Sun", "2026-09-06", "", "Buffalo Bills", "", "Miami Dolphins",
         "2026-09-06", "24", "21", "", "", "", "", "", "", ""]
    pipeline.merge_week_rows(games, [r], week=1)
    assert _read(games) == [HEADER, r]
