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

def test_current_last5_reads_metric(monkeypatch):
    monkeypatch.setattr(pipeline, "METRICS_DIR", FIX / "metrics")
    # latest row strictly before the date
    assert pipeline.current_last5(2026, "Kansas City Chiefs", "2026-10-25") == 0.6
    assert pipeline.current_last5(2026, "Kansas City Chiefs", "2026-12-01") == 1.0
    assert pipeline.current_last5(2026, "Denver Broncos", "2026-10-18") == 0.4
    # a row dated ON before_date is not "before"
    assert pipeline.current_last5(2026, "Kansas City Chiefs", "2026-10-11") is None
    # row exists but games_considered < 5 (bye): not qualifying -> None
    assert pipeline.current_last5(2026, "Detroit Lions", "2026-12-01") is None
    # team with no qualifying row (fewer than 5 prior games) -> None
    assert pipeline.current_last5(2026, "Buffalo Bills", "2026-12-01") is None
    # no metric file for the season at all -> None
    assert pipeline.current_last5(2031, "Kansas City Chiefs", "2031-12-01") is None


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


def test_subprocess_failure_propagates(tmp_path, monkeypatch):
    _fake_repo(tmp_path, monkeypatch)

    def boom(cmd, **kw):
        raise pipeline.subprocess.CalledProcessError(1, cmd)

    monkeypatch.setattr(pipeline.subprocess, "run", boom)
    with pytest.raises(pipeline.subprocess.CalledProcessError):
        pipeline.regenerate_metrics(2026)
    with pytest.raises(pipeline.subprocess.CalledProcessError):
        pipeline.ingest_week(2026, 3)


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


def test_merge_creates_file_when_missing(tmp_path):
    games = tmp_path / "games" / "2026_games.csv"
    r = ["1", "Sun", "2026-09-06", "", "Buffalo Bills", "", "Miami Dolphins",
         "2026-09-06", "24", "21", "", "", "", "", "", "", ""]
    pipeline.merge_week_rows(games, [r], week=1)
    assert _read(games) == [HEADER, r]
