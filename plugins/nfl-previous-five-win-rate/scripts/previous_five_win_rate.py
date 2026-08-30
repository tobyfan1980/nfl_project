#!/usr/bin/env python3
"""Compute a team's prior five-game win rate from an NFL games CSV."""

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
    result: str
    win_value: float
    team_points: int
    opponent_points: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--games-file", type=Path, required=True, help="season games CSV path")
    parser.add_argument("--date", required=True, help="target date in YYYY-MM-DD format")
    parser.add_argument("--team", required=True, help="team name as written in the CSV")
    parser.add_argument(
        "--window",
        type=int,
        default=5,
        help="number of prior games to evaluate (default: 5)",
    )
    args = parser.parse_args()
    if args.window < 1:
        parser.error("--window must be at least 1")
    return args


def parse_iso_date(value: str) -> date:
    try:
        return datetime.strptime(value.strip(), "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError(f"invalid date '{value}'; expected YYYY-MM-DD") from exc


def load_team_games(games_file: Path, team: str, target_date: date) -> list[TeamGame]:
    if not games_file.exists():
        raise FileNotFoundError(f"games file not found: {games_file}")

    games: list[TeamGame] = []
    with games_file.open(newline="", encoding="utf-8") as source:
        reader = csv.reader(source)
        header = next(reader, None)
        if not header:
            raise ValueError(f"games file is empty: {games_file}")

        for row in reader:
            if len(row) <= LOSER_POINTS_INDEX:
                continue
            if not row[DATE_INDEX].strip() or not row[WINNER_INDEX].strip() or not row[LOSER_INDEX].strip():
                continue

            try:
                game_date = parse_iso_date(row[DATE_INDEX])
            except ValueError:
                continue

            if game_date >= target_date:
                continue

            winner = row[WINNER_INDEX].strip()
            loser = row[LOSER_INDEX].strip()
            if team not in {winner, loser}:
                continue

            try:
                winner_points = int(row[WINNER_POINTS_INDEX])
                loser_points = int(row[LOSER_POINTS_INDEX])
            except ValueError:
                continue

            if winner_points == loser_points:
                result = "tie"
                win_value = 0.5
                if team == winner:
                    opponent = loser
                    team_points = winner_points
                    opponent_points = loser_points
                else:
                    opponent = winner
                    team_points = loser_points
                    opponent_points = winner_points
            elif team == winner:
                result = "win"
                win_value = 1.0
                opponent = loser
                team_points = winner_points
                opponent_points = loser_points
            else:
                result = "loss"
                win_value = 0.0
                opponent = winner
                team_points = loser_points
                opponent_points = winner_points

            games.append(
                TeamGame(
                    game_date=game_date,
                    opponent=opponent,
                    result=result,
                    win_value=win_value,
                    team_points=team_points,
                    opponent_points=opponent_points,
                )
            )

    games.sort(key=lambda item: item.game_date)
    return games


def format_rate(games: list[TeamGame]) -> str:
    if not games:
        return "0.000"
    return f"{sum(game.win_value for game in games) / len(games):.3f}"


def summarize_record(games: list[TeamGame]) -> tuple[int, int, int]:
    wins = sum(1 for game in games if game.result == "win")
    losses = sum(1 for game in games if game.result == "loss")
    ties = sum(1 for game in games if game.result == "tie")
    return wins, losses, ties


def main() -> int:
    args = parse_args()
    team = args.team.strip()
    target_date = parse_iso_date(args.date)
    team_games = load_team_games(args.games_file, team, target_date)
    selected_games = team_games[-args.window :]

    print(f"team: {team}")
    print(f"target_date: {target_date.isoformat()}")
    print(f"games_file: {args.games_file}")
    print(f"games_considered: {len(selected_games)}")

    if not selected_games:
        print("previous_games: none")
        print("record: 0-0-0")
        print("win_rate: 0.000")
        return 0

    wins, losses, ties = summarize_record(selected_games)
    print("previous_games:")
    for game in selected_games:
        print(
            f"- {game.game_date.isoformat()} vs {game.opponent}: "
            f"{game.result.upper()} ({game.team_points}-{game.opponent_points})"
        )
    print(f"record: {wins}-{losses}-{ties}")
    print(f"win_rate: {format_rate(selected_games)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
