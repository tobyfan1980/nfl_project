#!/usr/bin/env python3
"""Find the day gap between a team's prior completed game and a next-game date."""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path


DATE_INDEX = 2
WINNER_INDEX = 4
LOSER_INDEX = 6
WINNER_POINTS_INDEX = 8
LOSER_POINTS_INDEX = 9


@dataclass(frozen=True)
class TeamGame:
    game_date: date
    opponent: str
    team_points: int
    opponent_points: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--games-file", type=Path, required=True, help="season games CSV path")
    parser.add_argument("--team", required=True, help="team name as written in the CSV")
    parser.add_argument(
        "--next-game-date",
        required=True,
        help="next game date in YYYY-MM-DD format",
    )
    return parser.parse_args()


def parse_iso_date(value: str) -> date:
    try:
        return datetime.strptime(value.strip(), "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError(f"invalid date '{value}'; expected YYYY-MM-DD") from exc


def load_previous_game(games_file: Path, team: str, next_game_date: date) -> TeamGame | None:
    if not games_file.exists():
        raise FileNotFoundError(f"games file not found: {games_file}")

    previous_game: TeamGame | None = None
    with games_file.open(newline="", encoding="utf-8") as source:
        reader = csv.reader(source)
        header = next(reader, None)
        if not header:
            raise ValueError(f"games file is empty: {games_file}")

        for row in reader:
            if len(row) <= LOSER_POINTS_INDEX:
                continue

            game_date_value = row[DATE_INDEX].strip()
            winner = row[WINNER_INDEX].strip()
            loser = row[LOSER_INDEX].strip()
            if not game_date_value or team not in {winner, loser}:
                continue

            try:
                game_date = parse_iso_date(game_date_value)
            except ValueError:
                # Some source exports include malformed scheduled or postseason rows.
                continue
            if game_date >= next_game_date:
                continue

            try:
                winner_points = int(row[WINNER_POINTS_INDEX])
                loser_points = int(row[LOSER_POINTS_INDEX])
            except ValueError:
                # Scheduled or incomplete rows do not represent a prior completed game.
                continue

            if team == winner:
                candidate = TeamGame(game_date, loser, winner_points, loser_points)
            else:
                candidate = TeamGame(game_date, winner, loser_points, winner_points)

            if previous_game is None or candidate.game_date > previous_game.game_date:
                previous_game = candidate

    return previous_game


def main() -> int:
    args = parse_args()
    team = args.team.strip()
    next_game_date = parse_iso_date(args.next_game_date)
    previous_game = load_previous_game(args.games_file, team, next_game_date)

    print(f"team: {team}")
    print(f"next_game_date: {next_game_date.isoformat()}")
    print(f"games_file: {args.games_file}")

    if previous_game is None:
        print("previous_game: none")
        print("days_between_games: unavailable")
        return 0

    day_gap = (next_game_date - previous_game.game_date).days
    print(
        "previous_game: "
        f"{previous_game.game_date.isoformat()} vs {previous_game.opponent} "
        f"({previous_game.team_points}-{previous_game.opponent_points})"
    )
    print(f"days_between_games: {day_gap}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
