#!/usr/bin/env python3
"""Generate opponent-strength features for regular-season Weeks 6 through 18."""

from __future__ import annotations

import argparse
import csv
import tempfile
from dataclasses import dataclass
from pathlib import Path

from opponent_strength import (
    DATE_INDEX,
    LOSER_INDEX,
    LOSER_POINTS_INDEX,
    WINDOW,
    WINNER_INDEX,
    WINNER_POINTS_INDEX,
    load_games,
    opponent_for,
    parse_iso_date,
    team_games_before,
    wins_in_window,
)


FIRST_WEEK = 6
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
        help="directory for yyyy_opp_strength.csv files (default: dev_data/metrics)",
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

        for row_number, row in enumerate(reader, start=2):
            if len(row) <= LOSER_POINTS_INDEX:
                continue
            try:
                week = int(row[0])
            except ValueError:
                continue
            if not FIRST_WEEK <= week <= LAST_WEEK:
                continue
            try:
                game_date = parse_iso_date(row[DATE_INDEX])
                int(row[WINNER_POINTS_INDEX])
                int(row[LOSER_POINTS_INDEX])
            except ValueError as exc:
                raise ValueError(
                    f"invalid completed-game data at {games_file}:{row_number}"
                ) from exc

            winner = row[WINNER_INDEX].strip()
            loser = row[LOSER_INDEX].strip()
            if winner and loser:
                targets.append(TargetGame(week, game_date.isoformat(), winner, loser))

    return sorted(targets, key=lambda target: (target.week, target.game_date, target.winner))


def build_rows(games_file: Path, targets: list[TargetGame]) -> list[dict[str, str]]:
    games = load_games(games_file)
    rows: list[dict[str, str]] = []
    cache: dict[tuple[str, str], float] = {}

    for target in targets:
        cutoff = parse_iso_date(target.game_date)
        for team in (target.winner, target.loser):
            cache_key = (team, target.game_date)
            if cache_key not in cache:
                selected_games = team_games_before(games, team, cutoff)[-WINDOW:]
                rates: list[float] = []
                for previous_game in selected_games:
                    previous_opponent = opponent_for(previous_game, team)
                    wins, _ = wins_in_window(games, previous_opponent, cutoff)
                    rates.append(wins / WINDOW)
                cache[cache_key] = sum(rates) / len(rates) if rates else 0.0

            rows.append(
                {
                    "week": str(target.week),
                    "date": target.game_date,
                    "team": team,
                    "opponent_strength_average_win_rate": f"{cache[cache_key]:.3f}",
                }
            )

    return rows


def fieldnames() -> list[str]:
    return ["week", "date", "team", "opponent_strength_average_win_rate"]


def validate_rows(rows: list[dict[str, str]], target_count: int) -> None:
    if len(rows) != target_count * 2:
        raise ValueError(f"expected {target_count * 2} rows, built {len(rows)}")
    keys = {(row["date"], row["team"]) for row in rows}
    if len(keys) != len(rows):
        raise ValueError("duplicate date/team rows detected")
    for row in rows:
        if not FIRST_WEEK <= int(row["week"]) <= LAST_WEEK:
            raise ValueError(f"week outside requested range: {row['week']}")
        average = float(row["opponent_strength_average_win_rate"])
        if not 0.0 <= average <= 1.0:
            raise ValueError(f"opponent strength outside [0, 1]: {average}")


def write_rows(output_file: Path, rows: list[dict[str, str]]) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", newline="", encoding="utf-8", dir=output_file.parent, delete=False
    ) as temporary:
        writer = csv.DictWriter(temporary, fieldnames=fieldnames())
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
        output_file = args.output_dir / f"{year}_opp_strength.csv"
        if not games_file.exists():
            raise FileNotFoundError(f"games file not found: {games_file}")
        if output_file.exists() and not args.overwrite:
            raise FileExistsError(f"output exists: {output_file}; rerun with --overwrite")

        targets = load_targets(games_file)
        rows = build_rows(games_file, targets)
        validate_rows(rows, len(targets))
        write_rows(output_file, rows)
        print(f"{year}: wrote {len(rows)} rows to {output_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
