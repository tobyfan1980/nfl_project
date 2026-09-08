#!/usr/bin/env python3
"""Generate previous-game calendar-day intervals for regular-season Weeks 2 through 18."""

from __future__ import annotations

import argparse
import csv
import tempfile
from dataclasses import dataclass
from pathlib import Path

from previous_game_gap import (
    DATE_INDEX,
    LOSER_INDEX,
    LOSER_POINTS_INDEX,
    WINNER_INDEX,
    WINNER_POINTS_INDEX,
    load_previous_game,
    parse_iso_date,
)


WEEK_INDEX = 0
FIRST_WEEK = 2
LAST_WEEK = 18


@dataclass(frozen=True)
class TargetGame:
    week: int
    game_date: str
    winner: str
    loser: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("dev_data/games"),
        help="directory containing yyyy_games.csv files (default: dev_data/games)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("dev_data/metrics"),
        help="directory for yyyy_game_intervals.csv files (default: dev_data/metrics)",
    )
    parser.add_argument("--years", nargs="+", type=int, help="years to process")
    parser.add_argument("--overwrite", action="store_true", help="replace existing output files")
    return parser.parse_args()


def discover_years(input_dir: Path) -> list[int]:
    years = []
    for games_file in input_dir.glob("*_games.csv"):
        prefix = games_file.name.removesuffix("_games.csv")
        if prefix.isdigit() and len(prefix) == 4:
            years.append(int(prefix))
    return sorted(years)


def load_targets(games_file: Path) -> list[TargetGame]:
    targets: list[TargetGame] = []
    with games_file.open(newline="", encoding="utf-8") as source:
        reader = csv.reader(source)
        if not next(reader, None):
            raise ValueError(f"games file is empty: {games_file}")

        for row in reader:
            if len(row) <= LOSER_POINTS_INDEX:
                continue
            try:
                week = int(row[WEEK_INDEX])
                game_date = parse_iso_date(row[DATE_INDEX])
                int(row[WINNER_POINTS_INDEX])
                int(row[LOSER_POINTS_INDEX])
            except ValueError:
                continue
            if not FIRST_WEEK <= week <= LAST_WEEK:
                continue

            winner = row[WINNER_INDEX].strip()
            loser = row[LOSER_INDEX].strip()
            if winner and loser:
                targets.append(TargetGame(week, game_date.isoformat(), winner, loser))

    return sorted(targets, key=lambda target: (target.week, target.game_date, target.winner, target.loser))


def classify_rest_period(days: int) -> str:
    if 4 <= days <= 5:
        return "limited rest"
    if 6 <= days <= 8:
        return "regular rest"
    if 9 <= days <= 12:
        return "more rest"
    if days > 12:
        return "excessive rest"
    return ""


def build_rows(games_file: Path, targets: list[TargetGame]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    previous_games = {}
    for target in targets:
        game_date = parse_iso_date(target.game_date)
        for team, opponent in ((target.winner, target.loser), (target.loser, target.winner)):
            cache_key = (team, target.game_date)
            if cache_key not in previous_games:
                previous_games[cache_key] = load_previous_game(games_file, team, game_date)
            previous_game = previous_games[cache_key]
            if previous_game is None:
                continue
            days = (game_date - previous_game.game_date).days
            rows.append(
                {
                    "week": str(target.week),
                    "date": target.game_date,
                    "team": team,
                    "opponent": opponent,
                    "previous_game_date": previous_game.game_date.isoformat(),
                    "days_between_games": str(days),
                    "rest_period": classify_rest_period(days),
                }
            )
    return rows


def write_rows(output_file: Path, rows: list[dict[str, str]]) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "week",
        "date",
        "team",
        "opponent",
        "previous_game_date",
        "days_between_games",
        "rest_period",
    ]
    with tempfile.NamedTemporaryFile(
        "w", newline="", encoding="utf-8", dir=output_file.parent, delete=False
    ) as temporary:
        writer = csv.DictWriter(temporary, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
        temporary_path = Path(temporary.name)
    temporary_path.replace(output_file)


def main() -> int:
    args = parse_args()
    years = args.years or discover_years(args.input_dir)
    if not years:
        raise ValueError(f"no yyyy_games.csv files found in {args.input_dir}")

    for year in years:
        games_file = args.input_dir / f"{year}_games.csv"
        output_file = args.output_dir / f"{year}_game_intervals.csv"
        if not games_file.exists():
            raise FileNotFoundError(f"games file not found: {games_file}")
        if output_file.exists() and not args.overwrite:
            raise FileExistsError(f"output exists: {output_file}; rerun with --overwrite")

        rows = build_rows(games_file, load_targets(games_file))
        write_rows(output_file, rows)
        print(f"{year}: wrote {len(rows)} rows to {output_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
