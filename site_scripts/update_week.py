"""PocketPicks weekly update: ingest -> metrics -> results -> predict -> site data.

    python site_scripts/update_week.py --season 2026 --week 7 [--skip-ingest] [--data-dir site/data]

Run once a week (Tuesday). The script does the prediction AND writes the page
data (``week_NN.json``, ``results.json``, ``accuracy.json``, ``season.json``,
``injuries.json``) into ``--data-dir``. Publishing is a separate manual step:
``git add site/data && git commit && git push`` - the push is what updates the
live GitHub Pages site.

Steps, in order:

 1. load season.json (the new ``current_week`` is written last, so a failed
    run never leaves the site pointing at a week with no page)
 2. ingest last week's finished games (skipped with ``--skip-ingest``)
 3. regenerate the metric CSVs (win_rate is critical)
 4. score the PREVIOUS week's stored picks into results.json
 5. recompute accuracy.json from scratch
 6. fetch the upcoming week's schedule
 7. predict each game from both teams' last-5 win rates; either rate missing
    (team still warming up) -> ``prediction: null``
 8. attach consensus odds (absent without an API key)
 9. fetch the injury report
10. write week_NN.json (+ the other data files)
11. print a summary

Idempotent per (season, week): records, streaks and last-5 lists are derived
only from games in weeks BEFORE ``--week``, so re-running a week (even after
its games were played) rebuilds the same page; unchanged files are not
rewritten.

Game-field derivation (``Team.record``/``streak``, ``last5_home``/``last5_away``)
comes from ``dev_data/games/{season}_games.csv``; see ``team_history``.
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

# Make sibling modules importable when run as ``python site_scripts/update_week.py``.
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pipeline  # noqa: E402
from accuracy import compute_accuracy  # noqa: E402
from fetch_injuries import fetch_injuries  # noqa: E402
from fetch_odds import fetch_odds  # noqa: E402
from fetch_schedule import TEAM_SLUGS, fetch_schedule  # noqa: E402
from pipeline import current_last5, ingest_week, regenerate_metrics  # noqa: E402
from predict import predict_home_win  # noqa: E402
from results import update_results  # noqa: E402

log = logging.getLogger("update_week")

DEFAULT_DATA_DIR = pipeline.REPO_ROOT / "site" / "data"
DEFAULT_MODEL_ACTIVE_FROM_WEEK = 6
LAST5_LEN = 5


def games_csv_path(season: int) -> Path:
    return pipeline._games_dir() / f"{season}_games.csv"


# ------------------------------------------------------------------ json io

def _read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


def _write_json(path: Path, body) -> str:
    """Atomically write ``body``; return 'created' / 'updated' / 'unchanged'."""
    text = json.dumps(body, indent=2, ensure_ascii=False) + "\n"
    old = path.read_text(encoding="utf-8") if path.exists() else None
    if old == text:
        return "unchanged"
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=path.parent, prefix=path.name + ".",
            suffix=".tmp", delete=False) as tmp:
        tmp.write(text)
        tmp_path = tmp.name
    os.replace(tmp_path, path)
    return "created" if old is None else "updated"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# --------------------------------------------- record / streak / last-5 data

def _num(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def team_history(games_csv: Path, before_week: int) -> dict[str, list[dict]]:
    """Per-team finished games from weeks < ``before_week``, oldest first.

    Each entry: ``{"opponent": full name, "result": W/L/T, "score": "own-opp",
    "home_away": "home"/"away"}``. Orientation follows results.py/pipeline.py:
    the blank-named column holds ``@`` when the WINNER was away; otherwise the
    winner is treated as home. Neutral-site games (``N`` marker) cannot be
    oriented from the CSV and are therefore labelled winner=home, loser=away.
    Non-numeric weeks (playoffs) are ignored. A missing file -> ``{}``.
    """
    history: dict[str, list[dict]] = {}
    if not Path(games_csv).exists():
        return history
    with Path(games_csv).open(newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader, None)
        rows = [r for r in reader if len(r) >= 10]
    rows = [(n, r) for r in rows if (n := _num(r[0])) is not None and n < before_week]
    rows.sort(key=lambda t: (t[0], t[1][2]))  # stable: week, then date
    for _, r in rows:
        winner, marker, loser = r[4].strip(), r[5].strip(), r[6].strip()
        pts_w, pts_l = _num(r[8]), _num(r[9])
        if pts_w is None or pts_l is None:
            continue
        winner_away = marker == "@"
        tie = pts_w == pts_l
        history.setdefault(winner, []).append({
            "opponent": loser, "result": "T" if tie else "W",
            "score": f"{pts_w}-{pts_l}", "home_away": "away" if winner_away else "home"})
        history.setdefault(loser, []).append({
            "opponent": winner, "result": "T" if tie else "L",
            "score": f"{pts_l}-{pts_w}", "home_away": "home" if winner_away else "away"})
    return history


def team_record_and_streak(games: list[dict]) -> tuple[str, str]:
    """('W-L' or 'W-L-T', 'W3'/'L1'/'T1') from oldest-first games.

    No games yet -> ('0-0', 'W0'): the contract regex needs a [WLT]<n> streak.
    """
    w = sum(g["result"] == "W" for g in games)
    l = sum(g["result"] == "L" for g in games)
    t = sum(g["result"] == "T" for g in games)
    record = f"{w}-{l}" + (f"-{t}" if t else "")
    if not games:
        return record, "W0"
    last = games[-1]["result"]
    n = 0
    for g in reversed(games):
        if g["result"] != last:
            break
        n += 1
    return record, f"{last}{n}"


def _last5(games: list[dict]) -> list[dict]:
    """Most recent first, at most 5, opponent as slug (unknown teams dropped)."""
    out = []
    for g in reversed(games):
        slug = TEAM_SLUGS.get(g["opponent"])
        if slug is None:
            log.warning("last5: unknown opponent %r; omitted", g["opponent"])
            continue
        out.append({"opponent": slug, "result": g["result"],
                    "score": g["score"], "home_away": g["home_away"]})
        if len(out) == LAST5_LEN:
            break
    return out


# ---------------------------------------------------------------- game build

def _team_block(name: str, slug: str, games: list[dict]) -> dict:
    record, streak = team_record_and_streak(games)
    return {"team": name, "slug": slug, "record": record, "streak": streak}


def _prediction(season: int, game: dict) -> dict | None:
    """Predictor output for ``game``, or None while either team is warming up."""
    kickoff_date = game["kickoff_utc"][:10]
    home = current_last5(season, game["home_team"], kickoff_date)
    away = current_last5(season, game["away_team"], kickoff_date)
    if home is None or away is None:
        return None
    p = predict_home_win(home, away)
    return {
        "home_win_prob": p["home_win_prob"],
        "away_win_prob": p["away_win_prob"],
        "favored": p["favored"],
        "home_last5_win_rate": home,
        "away_last5_win_rate": away,
        "diff": round(p["diff"], 6),  # strip float noise (rates have 3 dp)
        "model": p["model"],
    }


def build_games(season: int, schedule: list[dict], history: dict,
                odds: dict) -> list[dict]:
    games = []
    for g in sorted(schedule, key=lambda g: (g["kickoff_utc"], g["id"])):
        home_hist = history.get(g["home_team"], [])
        away_hist = history.get(g["away_team"], [])
        games.append({
            "id": g["id"],
            "kickoff_utc": g["kickoff_utc"],
            "home": _team_block(g["home_team"], g["home_slug"], home_hist),
            "away": _team_block(g["away_team"], g["away_slug"], away_hist),
            "prediction": _prediction(season, g),
            "odds": odds.get(g["id"]),
            "last5_home": _last5(home_hist),
            "last5_away": _last5(away_hist),
        })
    return games


# ---------------------------------------------------------------------- main

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="PocketPicks weekly update")
    ap.add_argument("--season", type=int, required=True)
    ap.add_argument("--week", type=int, required=True)
    ap.add_argument("--skip-ingest", action="store_true",
                    help="do not crawl last week's games (use the games CSV as is)")
    ap.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR,
                    help="where the site JSON is written (default: site/data)")
    args = ap.parse_args(argv)
    season, week, data_dir = args.season, args.week, Path(args.data_dir)
    prev_week = week - 1
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    # 1. season.json (written at the end).
    season_json = _read_json(data_dir / "season.json", {})
    new_season = {
        "season": season,
        "current_week": week,
        "model_active_from_week": season_json.get(
            "model_active_from_week", DEFAULT_MODEL_ACTIVE_FROM_WEEK),
    }

    # 2-3. last week's games, then metrics.
    if not args.skip_ingest and prev_week >= 1:
        ingest_week(season, prev_week)
    regenerate_metrics(season)

    # 4. score the previous week's stored picks.
    csv_path = games_csv_path(season)
    results = _read_json(data_dir / "results.json", {})
    prev_week_json = data_dir / f"week_{prev_week:02d}.json"
    if prev_week >= 1 and csv_path.exists() and prev_week_json.exists():
        results = update_results(results, season, prev_week, str(csv_path),
                                 str(prev_week_json))
    else:
        log.warning("results: nothing to score for week %s (need %s and %s)",
                    prev_week, prev_week_json.name, csv_path.name)

    # 5. accuracy, from scratch.
    accuracy = compute_accuracy(results, season)

    # 6. schedule (a game with no kickoff time yet is skipped, not fatal).
    schedule = fetch_schedule(season, week, skip_unscheduled=True)

    # 7-8. predictions + odds.
    history = team_history(csv_path, week)
    odds = fetch_odds(schedule) or {}
    games = build_games(season, schedule, history, odds)
    week_json = {"season": season, "week": week, "generated_at": _now(), "games": games}

    # 9. injuries.
    injuries = fetch_injuries()

    # 10. write: page first, season.json (the "go live" pointer) last.
    status = {}
    for name, body in (
            (f"week_{week:02d}.json", week_json),
            ("results.json", results),
            ("accuracy.json", accuracy),
            ("injuries.json", injuries),
            ("season.json", new_season)):
        status[name] = _write_json(data_dir / name, body)

    # 11. summary.
    predicted = sum(g["prediction"] is not None for g in games)
    print(f"PocketPicks {season} week {week}: {len(games)} games "
          f"({predicted} predicted, {len(games) - predicted} warming up, "
          f"{sum(g['odds'] is not None for g in games)} with odds)")
    for name, st in status.items():
        print(f"  {st:9s} {data_dir / name}")
    print("\nNothing is live yet. To publish, run:\n"
          "  git add site/data && git commit && git push\n"
          "(the push is what updates the GitHub Pages site)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
