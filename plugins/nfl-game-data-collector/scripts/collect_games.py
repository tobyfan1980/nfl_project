#!/usr/bin/env python3
"""Collect completed NFL games in nfl_project's season CSV format."""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import os
import re
import tempfile
import time
import urllib.error
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path


SCHEDULE_URL = "https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv"
PBP_URL = (
    "https://github.com/nflverse/nflverse-data/releases/download/"
    "pbp/play_by_play_{year}.csv.gz"
)
ESPN_URLS = (
    "https://site.web.api.espn.com/apis/site/v2/sports/football/nfl/summary?event={event_id}",
    "https://cdn.espn.com/core/nfl/boxscore?xhr=1&gameId={event_id}",
)
USER_AGENT = "Mozilla/5.0 (compatible; NFLProjectDataCollector/1.0)"

HEADER = [
    "Week",
    "Day",
    "Date",
    "Time",
    "Winner/tie",
    "",
    "Loser/tie",
    "Date",
    "PtsW",
    "PtsL",
    "YdsW",
    "TOW",
    "YdsL",
    "TOL",
    "zipcode",
    "temperature",
    "condition",
]

TEAM_NAMES = {
    "ARI": "Arizona Cardinals",
    "ATL": "Atlanta Falcons",
    "BAL": "Baltimore Ravens",
    "BUF": "Buffalo Bills",
    "CAR": "Carolina Panthers",
    "CHI": "Chicago Bears",
    "CIN": "Cincinnati Bengals",
    "CLE": "Cleveland Browns",
    "DAL": "Dallas Cowboys",
    "DEN": "Denver Broncos",
    "DET": "Detroit Lions",
    "GB": "Green Bay Packers",
    "HOU": "Houston Texans",
    "IND": "Indianapolis Colts",
    "JAX": "Jacksonville Jaguars",
    "KC": "Kansas City Chiefs",
    "LV": "Las Vegas Raiders",
    "LAC": "Los Angeles Chargers",
    "LA": "Los Angeles Rams",
    "MIA": "Miami Dolphins",
    "MIN": "Minnesota Vikings",
    "NE": "New England Patriots",
    "NO": "New Orleans Saints",
    "NYG": "New York Giants",
    "NYJ": "New York Jets",
    "PHI": "Philadelphia Eagles",
    "PIT": "Pittsburgh Steelers",
    "SF": "San Francisco 49ers",
    "SEA": "Seattle Seahawks",
    "TB": "Tampa Bay Buccaneers",
    "TEN": "Tennessee Titans",
    "WAS": "Washington Commanders",
}
ESPN_TEAM_ALIASES = {"LAR": "LA", "WSH": "WAS"}
PLAYOFF_LABELS = {"WC": "WildCard", "DIV": "Division", "CON": "ConfChamp", "SB": "SuperBowl"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, required=True, help="NFL season year")
    parser.add_argument("--repo", type=Path, default=Path.cwd(), help="nfl_project repository root")
    parser.add_argument(
        "--output", type=Path, help="output path; defaults to dev_data/games/<year>_games.csv"
    )
    parser.add_argument("--cache-dir", type=Path, help="persistent source cache directory")
    parser.add_argument("--workers", type=int, default=6, help="concurrent ESPN requests (default: 6)")
    parser.add_argument("--overwrite", action="store_true", help="replace an existing output file")
    parser.add_argument("--skip-weather", action="store_true", help="leave weather columns blank")
    args = parser.parse_args()
    if args.workers < 1 or args.workers > 12:
        parser.error("--workers must be between 1 and 12")
    return args


def request_bytes(url: str, timeout: int = 60) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def download(url: str, destination: Path) -> Path:
    if destination.exists() and destination.stat().st_size:
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    part = destination.with_suffix(destination.suffix + ".part")
    last_error: Exception | None = None
    for attempt in range(4):
        try:
            part.write_bytes(request_bytes(url, timeout=120))
            if not part.stat().st_size:
                raise RuntimeError("download was empty")
            os.replace(part, destination)
            return destination
        except Exception as exc:
            last_error = exc
            part.unlink(missing_ok=True)
            if attempt < 3:
                time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"Failed to download {url}: {last_error}")


def load_schedule(path: Path, year: int) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as source:
        rows = [row for row in csv.DictReader(source) if row["season"] == str(year)]
    completed = [row for row in rows if row["home_score"] and row["away_score"]]
    if not completed:
        raise RuntimeError(f"No completed games found for the {year} season")
    missing_ids = [row["game_id"] for row in completed if not row["espn"]]
    if missing_ids:
        raise RuntimeError(f"Completed games lack ESPN IDs: {', '.join(missing_ids)}")
    return completed


def load_zipcodes(repo: Path) -> dict[str, str]:
    path = repo / "dev_data" / "nfl_teams_stadium_zip_only_5digit_text.csv"
    if not path.exists():
        raise RuntimeError(f"Missing team ZIP mapping: {path}")
    with path.open(newline="", encoding="utf-8") as source:
        mapping = {
            row["Team"].strip(): row["Stadium ZIP Code"].strip()
            for row in csv.DictReader(source)
        }
    missing = sorted(set(TEAM_NAMES.values()) - set(mapping))
    if missing:
        raise RuntimeError(f"ZIP mapping lacks teams: {', '.join(missing)}")
    return mapping


def load_weather(path: Path | None) -> dict[str, dict[str, str]]:
    if path is None:
        return {}
    weather: dict[str, dict[str, str]] = {}
    with gzip.open(path, "rt", newline="", encoding="utf-8") as source:
        for row in csv.DictReader(source):
            game_id = row["game_id"]
            if not game_id:
                continue
            item = weather.setdefault(game_id, {"temp": "", "weather": ""})
            if not item["temp"] and row["temp"]:
                item["temp"] = row["temp"]
            if not item["weather"] and row["weather"]:
                item["weather"] = row["weather"].strip()
    return weather


def parse_boxscore(payload: dict, expected_teams: set[str]) -> dict[str, dict[str, int]]:
    package = payload.get("gamepackageJSON", payload)
    teams = package.get("boxscore", {}).get("teams", [])
    stats: dict[str, dict[str, int]] = {}
    for team_entry in teams:
        abbreviation = team_entry["team"]["abbreviation"]
        abbreviation = ESPN_TEAM_ALIASES.get(abbreviation, abbreviation)
        values = {
            item["name"]: item.get("displayValue", "")
            for item in team_entry.get("statistics", [])
        }
        stats[abbreviation] = {
            "yards": int(values["totalYards"].replace(",", "")),
            "turnovers": int(values["turnovers"]),
        }
    if set(stats) != expected_teams:
        raise ValueError(f"expected teams {sorted(expected_teams)}, received {sorted(stats)}")
    return stats


def fetch_boxscore(game: dict[str, str]) -> tuple[str, dict[str, dict[str, int]]]:
    last_error: Exception | None = None
    for attempt in range(4):
        for template in ESPN_URLS:
            try:
                payload = json.loads(
                    request_bytes(template.format(event_id=game["espn"]), timeout=30)
                )
                expected = {game["home_team"], game["away_team"]}
                return game["game_id"], parse_boxscore(payload, expected)
            except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
                last_error = exc
        if attempt < 3:
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"{game['game_id']} ({game['espn']}): {last_error}")


def load_boxscores(games: list[dict[str, str]], cache_path: Path, workers: int) -> dict:
    boxscores = json.loads(cache_path.read_text()) if cache_path.exists() else {}
    pending = [game for game in games if game["game_id"] not in boxscores]
    failures: list[str] = []
    if pending:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [executor.submit(fetch_boxscore, game) for game in pending]
            for number, future in enumerate(as_completed(futures), 1):
                try:
                    game_id, stats = future.result()
                    boxscores[game_id] = stats
                except Exception as exc:
                    failures.append(str(exc))
                if number % 50 == 0 or number == len(pending):
                    print(
                        f"Box scores: {number}/{len(pending)} fetched; "
                        f"failures={len(failures)}"
                    )
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(
            json.dumps(boxscores, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    if failures:
        raise RuntimeError("Box-score fetch failures:\n" + "\n".join(failures))
    missing = [game["game_id"] for game in games if game["game_id"] not in boxscores]
    if missing:
        raise RuntimeError(f"Missing box scores: {', '.join(missing)}")
    return boxscores


def format_time(value: str) -> str:
    parsed = datetime.strptime(value, "%H:%M")
    hour = parsed.hour % 12 or 12
    return f"{hour}:{parsed.minute:02d}{'AM' if parsed.hour < 12 else 'PM'}"


def format_temperature(meta: dict[str, str]) -> str:
    value = meta.get("temp", "")
    if not value:
        match = re.search(r"Temp:\s*(-?\d+(?:\.\d+)?)", meta.get("weather", ""))
        value = match.group(1) if match else ""
    return f"{float(value):.1f}" if value else ""


def format_condition(value: str) -> str:
    if not value or value.startswith("Temp:") or re.fullmatch(r"\d+", value):
        return ""
    return value.split(" Temp:", 1)[0].strip()


def build_rows(
    games: list[dict[str, str]],
    boxscores: dict,
    weather: dict[str, dict[str, str]],
    zipcodes: dict[str, str],
) -> list[list[str]]:
    games.sort(key=lambda row: (row["gameday"], row["gametime"], row["game_id"]))
    rows: list[list[str]] = []
    separator_added = False
    for game in games:
        if game["game_type"] != "REG" and not separator_added:
            rows.append([""] * len(HEADER))
            separator_added = True

        home, away = game["home_team"], game["away_team"]
        if home not in TEAM_NAMES or away not in TEAM_NAMES:
            raise RuntimeError(
                f"Unsupported team abbreviation in {game['game_id']}: {away}, {home}"
            )
        home_score, away_score = int(game["home_score"]), int(game["away_score"])
        if home_score >= away_score:
            winner, loser = home, away
        else:
            winner, loser = away, home
        marker = "N" if game["location"] == "Neutral" else ("@" if winner == away else "")
        stats = boxscores[game["game_id"]]
        meta = weather.get(game["game_id"], {"temp": "", "weather": ""})
        week = (
            game["week"]
            if game["game_type"] == "REG"
            else PLAYOFF_LABELS[game["game_type"]]
        )
        rows.append(
            [
                week,
                game["weekday"][:3],
                game["gameday"],
                format_time(game["gametime"]),
                TEAM_NAMES[winner],
                marker,
                TEAM_NAMES[loser],
                game["gameday"],
                str(max(home_score, away_score)),
                str(min(home_score, away_score)),
                str(stats[winner]["yards"]),
                str(stats[winner]["turnovers"]),
                str(stats[loser]["yards"]),
                str(stats[loser]["turnovers"]),
                zipcodes[TEAM_NAMES[home]],
                format_temperature(meta),
                format_condition(meta.get("weather", "")),
            ]
        )
    return rows


def validate_rows(rows: list[list[str]], expected_games: int) -> None:
    games = [row for row in rows if any(row)]
    if len(games) != expected_games:
        raise RuntimeError(f"Expected {expected_games} games, built {len(games)}")
    malformed = [index for index, row in enumerate(rows, 2) if len(row) != len(HEADER)]
    if malformed:
        raise RuntimeError(f"Malformed rows: {malformed[:10]}")
    required_indexes = (0, 1, 2, 3, 4, 6, 7, 8, 9, 10, 11, 12, 13, 14)
    incomplete = [
        index
        for index, row in enumerate(games, 2)
        if any(not row[column] for column in required_indexes)
    ]
    if incomplete:
        raise RuntimeError(f"Rows missing core fields: {incomplete[:10]}")
    if len({(row[2], row[4], row[6]) for row in games}) != len(games):
        raise RuntimeError("Duplicate date/team matchup detected")


def write_atomic(output: Path, rows: list[list[str]]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    try:
        with temporary.open("w", newline="", encoding="utf-8") as destination:
            writer = csv.writer(destination)
            writer.writerow(HEADER)
            writer.writerows(rows)
        os.replace(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)


def main() -> None:
    args = parse_args()
    repo = args.repo.resolve()
    output = (args.output or repo / "dev_data" / "games" / f"{args.year}_games.csv").resolve()
    if output.exists() and not args.overwrite:
        raise SystemExit(
            f"Output exists: {output}. Pass --overwrite only when replacement is intended."
        )

    cache_dir = (
        args.cache_dir or Path(tempfile.gettempdir()) / "nfl-game-data-collector"
    ).resolve()
    schedule_path = download(SCHEDULE_URL, cache_dir / "nfl_games.csv")
    games = load_schedule(schedule_path, args.year)
    weather_path = None
    if not args.skip_weather:
        weather_path = download(
            PBP_URL.format(year=args.year),
            cache_dir / f"play_by_play_{args.year}.csv.gz",
        )
    weather = load_weather(weather_path)
    boxscores = load_boxscores(
        games,
        cache_dir / f"espn_{args.year}_boxscores.json",
        args.workers,
    )
    rows = build_rows(games, boxscores, weather, load_zipcodes(repo))
    validate_rows(rows, len(games))
    write_atomic(output, rows)

    game_rows = [row for row in rows if any(row)]
    playoff_counts = Counter(row[0] for row in game_rows if not row[0].isdigit())
    print(f"Wrote {len(game_rows)} completed games to {output}")
    print(f"Regular season: {sum(row[0].isdigit() for row in game_rows)}")
    print(f"Postseason: {dict(playoff_counts)}")
    print(f"Temperature populated: {sum(bool(row[15]) for row in game_rows)}")
    print(f"Condition populated: {sum(bool(row[16]) for row in game_rows)}")
    print(f"Sources: {SCHEDULE_URL}, nflverse PBP release, ESPN box scores")


if __name__ == "__main__":
    main()
