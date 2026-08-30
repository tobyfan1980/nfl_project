#!/usr/bin/env python3
"""Calculate the average prior-five-game win rate of a team's prior opponents."""

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
WINDOW = 5


@dataclass(frozen=True)
class Game:
    game_date: date
    winner: str
    loser: str
    winner_points: int
    loser_points: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--games-file", type=Path, required=True, help="season games CSV path")
    parser.add_argument("--team", required=True, help="team name as written in the CSV")
    parser.add_argument("--current-date", required=True, help="cutoff date in YYYY-MM-DD format")
    return parser.parse_args()


def parse_iso_date(value: str) -> date:
    try:
        return datetime.strptime(value.strip(), "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError(f"invalid date '{value}'; expected YYYY-MM-DD") from exc


def load_games(games_file: Path) -> list[Game]:
    if not games_file.exists():
        raise FileNotFoundError(f"games file not found: {games_file}")

    games: list[Game] = []
    with games_file.open(newline="", encoding="utf-8") as source:
        reader = csv.reader(source)
        header = next(reader, None)
        if not header:
            raise ValueError(f"games file is empty: {games_file}")

        for row_number, row in enumerate(reader, start=2):
            if len(row) <= LOSER_POINTS_INDEX:
                continue
            try:
                game = Game(
                    game_date=parse_iso_date(row[DATE_INDEX]),
                    winner=row[WINNER_INDEX].strip(),
                    loser=row[LOSER_INDEX].strip(),
                    winner_points=int(row[WINNER_POINTS_INDEX]),
                    loser_points=int(row[LOSER_POINTS_INDEX]),
                )
            except ValueError:
                continue
            if not game.winner or not game.loser:
                continue
            games.append(game)
    return sorted(games, key=lambda game: game.game_date)


def team_games_before(games: list[Game], team: str, cutoff: date) -> list[Game]:
    return [
        game
        for game in games
        if game.game_date < cutoff and team in {game.winner, game.loser}
    ]


def opponent_for(game: Game, team: str) -> str:
    return game.loser if team == game.winner else game.winner


def wins_in_window(games: list[Game], team: str, cutoff: date) -> tuple[int, int]:
    previous_games = team_games_before(games, team, cutoff)[-WINDOW:]
    wins = sum(
        game.winner == team and game.winner_points != game.loser_points
        for game in previous_games
    )
    return wins, len(previous_games)


def main() -> int:
    args = parse_args()
    team = args.team.strip()
    cutoff = parse_iso_date(args.current_date)
    games = load_games(args.games_file)
    selected_games = team_games_before(games, team, cutoff)[-WINDOW:]

    print(f"team: {team}")
    print(f"current_date: {cutoff.isoformat()}")
    print(f"games_considered: {len(selected_games)}")
    if not selected_games:
        print("opponent_strength_average_win_rate: unavailable")
        return 0

    rates: list[float] = []
    print("opponents:")
    for game in selected_games:
        opponent = opponent_for(game, team)
        wins, games_available = wins_in_window(games, opponent, cutoff)
        win_rate = wins / WINDOW
        rates.append(win_rate)
        print(
            f"- {game.game_date.isoformat()} {opponent}: "
            f"{wins}/{WINDOW} = {win_rate:.3f} "
            f"({games_available} prior games available)"
        )

    print(f"opponent_strength_average_win_rate: {sum(rates) / len(rates):.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
