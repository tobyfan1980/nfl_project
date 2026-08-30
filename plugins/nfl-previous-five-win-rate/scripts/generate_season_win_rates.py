#!/usr/bin/env python3
"""Generate prior-five-game win-rate features for regular-season Weeks 6 through 18."""

from __future__ import annotations

import argparse
import csv
import tempfile
from dataclasses import dataclass
from pathlib import Path

from previous_five_win_rate import (
    DATE_INDEX,
    LOSER_INDEX,
    LOSER_POINTS_INDEX,
    WINNER_INDEX,
    WINNER_POINTS_INDEX,
    load_team_games,
    parse_iso_date,
    summarize_record,
)


FIRST_WEEK = 6
LAST_WEEK = 18


@dataclass(frozen=True)
class TargetGame:
    week: int
    game_date: str
    team: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("dev_data"),
        help="directory containing yyyy_games.csv files (default: dev_data)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("dev_data"),
        help="directory for yyyy_win_rate.csv files (default: dev_data)",
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
                week = int(row[0])
                parse_iso_date(row[DATE_INDEX])
                int(row[WINNER_POINTS_INDEX])
                int(row[LOSER_POINTS_INDEX])
            except ValueError:
                continue
            if not FIRST_WEEK <= week <= LAST_WEEK:
                continue
            winner = row[WINNER_INDEX].strip()
            loser = row[LOSER_INDEX].strip()
            if winner and loser:
                targets.extend(
                    [
                        TargetGame(week, row[DATE_INDEX].strip(), winner),
                        TargetGame(week, row[DATE_INDEX].strip(), loser),
                    ]
                )
    return sorted(targets, key=lambda target: (target.week, target.game_date, target.team))


def build_rows(games_file: Path, targets: list[TargetGame]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    cached_records: dict[tuple[str, str], tuple[int, int, int, float, int]] = {}
    for target in targets:
        cache_key = (target.team, target.game_date)
        if cache_key not in cached_records:
            previous_games = load_team_games(
                games_file, target.team, parse_iso_date(target.game_date)
            )[-5:]
            wins, losses, ties = summarize_record(previous_games)
            win_rate = sum(game.win_value for game in previous_games) / len(previous_games)
            cached_records[cache_key] = (wins, losses, ties, win_rate, len(previous_games))
        wins, losses, ties, win_rate, games_considered = cached_records[cache_key]
        rows.append(
            {
                "week": str(target.week),
                "date": target.game_date,
                "team": target.team,
                "games_considered": str(games_considered),
                "wins": str(wins),
                "losses": str(losses),
                "ties": str(ties),
                "win_rate": f"{win_rate:.3f}",
            }
        )
    return rows


def write_rows(output_file: Path, rows: list[dict[str, str]]) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    fields = ["week", "date", "team", "games_considered", "wins", "losses", "ties", "win_rate"]
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
        output_file = args.output_dir / f"{year}_win_rate.csv"
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
