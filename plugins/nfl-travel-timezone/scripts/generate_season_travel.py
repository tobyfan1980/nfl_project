#!/usr/bin/env python3
"""Generate prior-game travel and timezone features for regular-season Weeks 2 through 18."""

from __future__ import annotations

import argparse
import csv
import tempfile
from dataclasses import dataclass
from pathlib import Path

from calculate_travel import (
    DATE_INDEX,
    LOSER_INDEX,
    LOSER_POINTS_INDEX,
    MARKER_INDEX,
    WINNER_INDEX,
    WINNER_POINTS_INDEX,
    leg_summary,
    load_locations,
    offset_hours,
    parse_date,
    previous_game_before,
)


WEEK_INDEX = 0
ZIPCODE_INDEX = 14
FIRST_WEEK = 2
LAST_WEEK = 18


@dataclass(frozen=True)
class TargetGame:
    week: int
    game_date: str
    home_team: str
    away_team: str
    venue_type: str
    next_location: dict


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=Path("dev_data/games"))
    parser.add_argument("--output-dir", type=Path, default=Path("dev_data/metrics"))
    parser.add_argument("--years", nargs="+", type=int, help="years to process")
    parser.add_argument(
        "--team-zipcodes",
        type=Path,
        help="team stadium ZIP mapping; defaults to dev_data/reference/nfl_teams_stadium_zip_only_5digit_text.csv",
    )
    parser.add_argument("--overwrite", action="store_true", help="replace existing output files")
    return parser.parse_args()


def discover_years(input_dir: Path) -> list[int]:
    return sorted(
        int(path.name.removesuffix("_games.csv"))
        for path in input_dir.glob("*_games.csv")
        if path.name.removesuffix("_games.csv").isdigit()
        and len(path.name.removesuffix("_games.csv")) == 4
    )


def load_home_teams_by_zip(zipcodes_file: Path) -> dict[str, set[str]]:
    if not zipcodes_file.exists():
        raise FileNotFoundError(f"team ZIP mapping not found: {zipcodes_file}")
    teams_by_zip: dict[str, set[str]] = {}
    with zipcodes_file.open(newline="", encoding="utf-8") as source:
        for row in csv.DictReader(source):
            teams_by_zip.setdefault(row["Stadium ZIP Code"].strip().zfill(5), set()).add(
                row["Team"].strip()
            )
    return teams_by_zip


def home_and_away_teams(row: list[str], teams_by_zip: dict[str, set[str]]) -> tuple[str, str, str]:
    winner, loser, marker = row[WINNER_INDEX].strip(), row[LOSER_INDEX].strip(), row[MARKER_INDEX].strip()
    if marker == "@":
        return loser, winner, "stadium"
    if marker != "N":
        return winner, loser, "stadium"
    candidates = teams_by_zip.get(row[ZIPCODE_INDEX].strip().zfill(5), set()) & {winner, loser}
    if len(candidates) != 1:
        raise ValueError(f"cannot identify nominal home team for neutral game on {row[DATE_INDEX]}")
    home_team = candidates.pop()
    away_team = loser if home_team == winner else winner
    return home_team, away_team, "neutral"


def load_targets(
    games_file: Path,
    by_team: dict[str, dict],
    by_city: dict[str, dict],
    neutral_by_game: dict[tuple[str, frozenset[str]], str],
    teams_by_zip: dict[str, set[str]],
) -> list[TargetGame]:
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
                game_date = parse_date(row[DATE_INDEX].strip())
                int(row[WINNER_POINTS_INDEX])
                int(row[LOSER_POINTS_INDEX])
            except ValueError:
                continue
            if not FIRST_WEEK <= week <= LAST_WEEK:
                continue
            home_team, away_team, venue_type = home_and_away_teams(row, teams_by_zip)
            if venue_type == "stadium":
                next_location = by_team[home_team]
            else:
                city = neutral_by_game.get((game_date.isoformat(), frozenset((home_team, away_team))))
                next_location = by_city.get("" if city is None else "".join(character.lower() for character in city if character.isalnum()))
                if next_location is None:
                    raise ValueError(f"neutral game location is missing for {game_date.isoformat()}")
            targets.append(
                TargetGame(week, game_date.isoformat(), home_team, away_team, venue_type, next_location)
            )
    return sorted(targets, key=lambda target: (target.week, target.game_date, target.home_team))


def previous_location(previous, by_team, by_city, neutral_by_game):
    if previous.role != "neutral":
        return by_team[previous.venue_team]
    city = neutral_by_game.get((previous.game_date.isoformat(), previous.participants))
    if city is None:
        raise ValueError(f"neutral previous-game location is missing for {previous.game_date.isoformat()}")
    location = by_city.get("".join(character.lower() for character in city if character.isalnum()))
    if location is None:
        raise ValueError(f"neutral city is not in location catalog: {city}")
    return location


def route_for_game(team, next_role, next_location, previous, previous_location, home_location, game_date):
    if next_role == "home":
        legs = [] if previous.role == "home" else [leg_summary(previous_location, home_location, game_date)]
        return legs, "already_home" if not legs else "previous_venue_to_home", home_location

    if previous.role == "home":
        return [leg_summary(home_location, next_location, game_date)], f"home_to_next_{next_role}", next_location

    direct = leg_summary(previous_location, next_location, game_date)
    via_home = [
        leg_summary(previous_location, home_location, game_date),
        leg_summary(home_location, next_location, game_date),
    ]
    if sum(leg["miles"] for leg in via_home) < 2 * direct["miles"]:
        return via_home, f"previous_venue_to_home_to_next_{next_role}", next_location
    return [direct], f"previous_venue_to_next_{next_role}", next_location


def build_rows(games_file, targets, by_team, by_city, neutral_by_game):
    rows: list[dict[str, str]] = []
    previous_cache = {}
    for target in targets:
        game_date = parse_date(target.game_date)
        for team, next_role in ((target.home_team, "home"), (target.away_team, "away")):
            opponent = target.away_team if team == target.home_team else target.home_team
            cache_key = (team, target.game_date)
            if cache_key not in previous_cache:
                previous_cache[cache_key] = previous_game_before(games_file, team, game_date)
            previous = previous_cache[cache_key]
            if previous is None:
                continue
            start_location = previous_location(previous, by_team, by_city, neutral_by_game)
            home_location = by_team[team]
            current_role = "neutral" if target.venue_type == "neutral" else next_role
            legs, route, destination = route_for_game(
                team, current_role, target.next_location, previous, start_location, home_location, game_date
            )
            travel_miles = round(sum(leg["miles"] for leg in legs))
            timezone_transition = sum(leg["timezone_transition"] for leg in legs)
            net_change = offset_hours(destination, game_date) - offset_hours(start_location, game_date)
            rows.append(
                {
                    "week": str(target.week),
                    "date": target.game_date,
                    "team": team,
                    "opponent": opponent,
                    "team_role": next_role,
                    "game_venue_type": target.venue_type,
                    "previous_game_date": previous.game_date.isoformat(),
                    "previous_game_role": previous.role,
                    "previous_city": start_location["city"],
                    "next_city": destination["city"],
                    "route": route,
                    "travel_miles": str(travel_miles),
                    "timezone_transition_hours": f"{timezone_transition:g}",
                    "net_timezone_change_hours": f"{net_change:+g}",
                }
            )
    return rows


def write_rows(output_file: Path, rows: list[dict[str, str]]) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "week", "date", "team", "opponent", "team_role", "game_venue_type", "previous_game_date",
        "previous_game_role", "previous_city", "next_city", "route", "travel_miles",
        "timezone_transition_hours", "net_timezone_change_hours",
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
    zipcodes_file = args.team_zipcodes or Path(
        "dev_data/reference/nfl_teams_stadium_zip_only_5digit_text.csv"
    )
    teams_by_zip = load_home_teams_by_zip(zipcodes_file)
    by_team, by_city, neutral_by_game = load_locations()
    for year in years:
        games_file = args.input_dir / f"{year}_games.csv"
        output_file = args.output_dir / f"{year}_travel-timezone.csv"
        if not games_file.exists():
            raise FileNotFoundError(f"games file not found: {games_file}")
        if output_file.exists() and not args.overwrite:
            raise FileExistsError(f"output exists: {output_file}; rerun with --overwrite")
        rows = build_rows(
            games_file,
            load_targets(games_file, by_team, by_city, neutral_by_game, teams_by_zip),
            by_team,
            by_city,
            neutral_by_game,
        )
        write_rows(output_file, rows)
        print(f"{year}: wrote {len(rows)} rows to {output_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
