"""PocketPicks data-pipeline wrappers.

Thin wrappers around the repo's EXISTING crawler and metric generators so the
weekly update owns the full data pipeline for a season:

* ``ingest_week``        - run ``tools/nfl_crawler.py`` and merge its output
                           into ``dev_data/games/{season}_games.csv``.
* ``regenerate_metrics`` - run the four plugin generators with ``--overwrite``
                           to rebuild ``dev_data/metrics/{season}_*.csv``.
* ``current_last5``      - compute a team's as-of-kickoff last-5 win rate
                           from the season games CSV.

All paths resolve from this file's location (not the cwd), and every
subprocess is run with ``cwd=REPO_ROOT`` because the crawler writes to a
cwd-relative ``dev_data/games/`` path.

Crawler -> season CSV conversion (known, deliberate limitations): the crawler
emits ``Date, Home Team, Away Team, scores, rushing/passing yards`` (no
winner/loser orientation, turnovers, kickoff time, weather, or neutral-site
flag), whereas the season CSV is the Pro-Football-Reference style
``Week,Day,Date,Time,Winner/tie,,Loser/tie,Date,PtsW,PtsL,YdsW,TOW,YdsL,TOL,
zipcode,temperature,condition``. Conversion derives winner/loser from the
scores, the ``@`` marker (winner was away), ``Day`` from the date, total yards
(rush + pass) when both are present, and ``zipcode`` from the home team's
stadium. Time, turnovers, temperature and condition are left blank, and games
are never flagged ``N`` (neutral) because the crawler cannot tell. None of the
four metric generators read the blank columns (the travel generator reads
``zipcode`` only for ``N`` games).
"""
from __future__ import annotations

import csv
import logging
import os
import subprocess
import sys
import tempfile
from datetime import date, datetime
from pathlib import Path

log = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent
METRICS_DIR = REPO_ROOT / "dev_data" / "metrics"

SEASON_HEADER = ["Week", "Day", "Date", "Time", "Winner/tie", "", "Loser/tie",
                 "Date", "PtsW", "PtsL", "YdsW", "TOW", "YdsL", "TOL", "zipcode",
                 "temperature", "condition"]

# (plugin dir, generator script) - order = metric file build order.
# win_rate runs FIRST and is the only CRITICAL one (the live site uses it);
# the rest are best-effort (see regenerate_metrics).
CRITICAL_PLUGIN = "nfl-previous-five-win-rate"
GENERATORS = [
    (CRITICAL_PLUGIN, "generate_season_win_rates.py"),
    ("nfl-opponent-strength", "generate_season_opponent_strength.py"),
    ("nfl-previous-game-gap", "generate_season_game_intervals.py"),
    ("nfl-travel-timezone", "generate_season_travel.py"),
]

# Plugin scripts live next to this package regardless of REPO_ROOT overrides.
PLUGIN_SCRIPTS = (Path(__file__).resolve().parent.parent / "plugins"
                  / CRITICAL_PLUGIN / "scripts")

ZIPCODES_RELPATH = Path("dev_data") / "reference" / "nfl_teams_stadium_zip_only_5digit_text.csv"


def _games_dir() -> Path:
    return REPO_ROOT / "dev_data" / "games"


# ----------------------------------------------------------------- ingest

def load_stadium_zipcodes() -> dict[str, str]:
    """Team full name -> 5-digit stadium ZIP (blank map if the file is absent)."""
    path = REPO_ROOT / ZIPCODES_RELPATH
    if not path.exists():
        return {}
    with path.open(newline="", encoding="utf-8") as f:
        return {r["Team"].strip(): r["Stadium ZIP Code"].strip().zfill(5)
                for r in csv.DictReader(f)}


def _int_or_none(value) -> int | None:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _total_yards(rush, passing) -> str:
    r, p = _int_or_none(rush), _int_or_none(passing)
    return "" if r is None or p is None else str(r + p)


def convert_crawler_rows(crawler_rows: list[dict], week: int,
                         zipcodes: dict[str, str]) -> list[list[str]]:
    """Convert crawler output rows (dicts) to season-CSV rows (lists of str).

    The crawler only emits decided games (winner/loser rows are required), so a
    tie never appears; equal scores are treated as home-team "winner" with no
    marker.
    """
    out = []
    for g in crawler_rows:
        home, away = g["Home Team"].strip(), g["Away Team"].strip()
        hs, as_ = _int_or_none(g["Home Score"]), _int_or_none(g["Away Score"])
        if hs is None or as_ is None:
            continue
        day = datetime.strptime(g["Date"], "%Y-%m-%d").strftime("%a")
        h_yds = _total_yards(g.get("Home Rushing Yards"), g.get("Home Passing Yards"))
        a_yds = _total_yards(g.get("Away Rushing Yards"), g.get("Away Passing Yards"))
        if as_ > hs:  # away team won
            winner, loser, marker = away, home, "@"
            pw, pl, yw, yl = as_, hs, a_yds, h_yds
        else:
            winner, loser, marker = home, away, ""
            pw, pl, yw, yl = hs, as_, h_yds, a_yds
        out.append([str(week), day, g["Date"], "", winner, marker, loser, g["Date"],
                    str(pw), str(pl), yw, "", yl, "", zipcodes.get(home, ""), "", ""])
    return out


def _game_key(row: list[str]) -> tuple:
    # Numeric week when parseable ("03" / "3.0" == "3"); raw string otherwise.
    n = _int_or_none(row[0])
    return (n if n is not None else row[0], frozenset((row[4], row[6])), row[2])


def merge_week_rows(games_file: Path, new_rows: list[list[str]], week: int) -> None:
    """Merge season-format rows into ``games_file``.

    Existing rows for ``week`` are replaced wholesale by ``new_rows``; rows for
    other weeks are kept. The result is deduped on (week, {winner, loser},
    date) (first occurrence wins) and stably sorted by numeric week.
    """
    games_file = Path(games_file)
    header, kept = SEASON_HEADER, []
    if games_file.exists():
        with games_file.open(newline="", encoding="utf-8") as f:
            existing = list(csv.reader(f))
        if existing:
            header = existing[0]
            # Numeric week compare; non-numeric (playoff) rows are always kept.
            kept = [r for r in existing[1:]
                    if r and _int_or_none(r[0]) != int(week)]

    seen, merged = set(), []
    for r in kept + list(new_rows):
        if len(r) < 7:
            continue
        key = _game_key(r)
        if key in seen:
            continue
        seen.add(key)
        merged.append(r)

    def week_order(r):
        n = _int_or_none(r[0])
        return (0, n) if n is not None else (1, 0)

    merged.sort(key=week_order)

    games_file.parent.mkdir(parents=True, exist_ok=True)
    # Atomic write: a crash mid-write must not truncate the real games file.
    with tempfile.NamedTemporaryFile(
            "w", newline="", encoding="utf-8", dir=games_file.parent,
            prefix=games_file.name + ".", suffix=".tmp", delete=False) as tmp:
        w = csv.writer(tmp)
        w.writerow(header)
        w.writerows(merged)
        tmp_path = tmp.name
    os.replace(tmp_path, games_file)


def ingest_week(season: int, week: int) -> None:
    """Crawl one week and merge it into ``dev_data/games/{season}_games.csv``.

    Raises ``subprocess.CalledProcessError`` if the crawler fails, and
    ``RuntimeError`` if it exits 0 without producing output (it prints an
    error and returns 0 when no game data was retrieved).
    """
    crawler_out = _games_dir() / f"nfl_{season}_week_{week}_game_stats.csv"
    crawler_out.unlink(missing_ok=True)  # a stale file must not mask a failed crawl
    subprocess.run(
        [sys.executable, str(REPO_ROOT / "tools" / "nfl_crawler.py"),
         "--year", str(season), "--week", str(week)],
        check=True, cwd=str(REPO_ROOT),
    )
    if not crawler_out.exists():
        raise RuntimeError(
            f"crawler produced no output for {season} week {week} "
            f"(expected {crawler_out})")
    with crawler_out.open(newline="", encoding="utf-8") as f:
        crawled = list(csv.DictReader(f))
    rows = convert_crawler_rows(crawled, week, load_stadium_zipcodes())
    if not rows:
        raise RuntimeError(f"crawler output for {season} week {week} had no usable games")
    merge_week_rows(_games_dir() / f"{season}_games.csv", rows, week)


# ------------------------------------------------------------- metrics

def regenerate_metrics(season: int) -> None:
    """Rebuild ``dev_data/metrics/{season}_*.csv`` with every plugin generator.

    ``nfl-previous-five-win-rate`` (win_rate) is CRITICAL: if it fails the
    error propagates. The other generators are BEST-EFFORT: a
    ``CalledProcessError`` is logged as a warning and the run continues, so a
    known-broken generator (e.g. travel's missing stadium-locations json)
    cannot stop win_rate from being regenerated.

    Each generator is run as a script (so its own ``scripts/`` dir is
    ``sys.path[0]`` and sibling imports resolve) from ``cwd=REPO_ROOT`` with
    absolute ``--input-dir``/``--output-dir`` and ``--overwrite``.
    """
    games = str(_games_dir())
    metrics = str(REPO_ROOT / "dev_data" / "metrics")
    for plugin, script in GENERATORS:
        cmd = [sys.executable,
               str(REPO_ROOT / "plugins" / plugin / "scripts" / script),
               "--input-dir", games, "--output-dir", metrics,
               "--years", str(season), "--overwrite"]
        if plugin == "nfl-travel-timezone":
            cmd += ["--team-zipcodes", str(REPO_ROOT / ZIPCODES_RELPATH)]
        try:
            subprocess.run(cmd, check=True, cwd=str(REPO_ROOT))
        except subprocess.CalledProcessError as exc:
            if plugin == CRITICAL_PLUGIN:
                raise
            log.warning("best-effort metric generator %s failed for %s "
                        "(exit %s); continuing", script, season, exc.returncode)


# --------------------------------------------------------------- reader

def _load_last5_plugin():
    """Import the win-rate plugin script (its scripts dir is put on sys.path,
    mirroring how the generators are run as scripts)."""
    scripts = str(PLUGIN_SCRIPTS)
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    import previous_five_win_rate
    return previous_five_win_rate


def current_last5(season: int, team_full: str, before_date: str) -> float | None:
    """True as-of-kickoff last-5 win rate for ``team_full``.

    Computed directly from ``{games_dir}/{season}_games.csv``: the 5 most
    recent COMPLETED games dated strictly before ``before_date``
    (``YYYY-MM-DD``), ``(wins + 0.5 * ties) / 5``. This matches the model's
    training definition ("the 5 games before the predicted game") and, unlike
    the pre-generated ``{season}_win_rate.csv`` rows (row dated D excludes D's
    game, so the latest row before a kickoff ignores the team's most recent
    game), includes the team's most recent finished game.

    Fewer than 5 qualifying games (warming up) or a missing games file ->
    ``None``. Game loading reuses the plugin's ``load_team_games`` (same
    parsing as the metric generator).
    """
    path = _games_dir() / f"{season}_games.csv"
    if not path.exists():
        return None
    plugin = _load_last5_plugin()
    games = plugin.load_team_games(path, team_full, date.fromisoformat(before_date))
    last5 = games[-5:]
    if len(last5) < 5:
        return None
    wins, _losses, ties = plugin.summarize_record(last5)
    return (wins + 0.5 * ties) / 5
