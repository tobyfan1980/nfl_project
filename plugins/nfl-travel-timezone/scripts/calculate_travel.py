#!/usr/bin/env python3
"""Calculate an NFL team's travel miles and timezone changes from its prior game."""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
from dataclasses import dataclass
from datetime import date, datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo


DATE_INDEX = 2
WINNER_INDEX = 4
MARKER_INDEX = 5
LOSER_INDEX = 6
WINNER_POINTS_INDEX = 8
LOSER_POINTS_INDEX = 9
EARTH_RADIUS_MILES = 3958.7613
LOCATIONS_FILE = Path(__file__).resolve().parents[1] / "references" / "nfl_stadium_locations.json"


@dataclass(frozen=True)
class PreviousGame:
    game_date: date
    role: str
    venue_team: str
    opponent: str
    participants: frozenset[str]


def normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def parse_date(value: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError(f"invalid date '{value}'; expected YYYY-MM-DD") from exc


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--games-file", type=Path, required=True)
    parser.add_argument("--team", required=True)
    parser.add_argument("--venue", required=True, choices=("home", "away"))
    parser.add_argument("--next-game-city", required=True)
    parser.add_argument("--next-game-date", help="optional YYYY-MM-DD date for timezone offsets")
    parser.add_argument(
        "--previous-game-city",
        help="required only when the latest completed prior game was neutral-site",
    )
    return parser.parse_args()


def load_locations() -> tuple[dict[str, dict], dict[str, dict], dict[tuple[str, frozenset[str]], str]]:
    catalog = json.loads(LOCATIONS_FILE.read_text(encoding="utf-8"))
    locations = catalog["locations"]
    by_team: dict[str, dict] = {}
    by_city: dict[str, dict] = {}
    for location in locations:
        for team in location["teams"]:
            by_team[team] = location
        for name in [location["city"], *location.get("aliases", [])]:
            by_city[normalize(name)] = location
    neutral_by_game = {
        (item["date"], frozenset(item["teams"])): item["city"]
        for item in catalog.get("neutral_games", [])
    }
    return by_team, by_city, neutral_by_game


def previous_game_before(
    games_file: Path, team: str, cutoff_date: date | None = None
) -> PreviousGame | None:
    if not games_file.exists():
        raise FileNotFoundError(f"games file not found: {games_file}")
    previous: PreviousGame | None = None
    with games_file.open(newline="", encoding="utf-8") as source:
        reader = csv.reader(source)
        if not next(reader, None):
            raise ValueError(f"games file is empty: {games_file}")
        for row_number, row in enumerate(reader, start=2):
            if len(row) <= LOSER_POINTS_INDEX:
                continue
            winner, loser = row[WINNER_INDEX].strip(), row[LOSER_INDEX].strip()
            if team not in {winner, loser}:
                continue
            try:
                int(row[WINNER_POINTS_INDEX])
                int(row[LOSER_POINTS_INDEX])
                game_date = parse_date(row[DATE_INDEX].strip())
            except ValueError:
                continue
            if cutoff_date is not None and game_date >= cutoff_date:
                continue
            marker = row[MARKER_INDEX].strip()
            if marker == "N":
                role, venue_team = "neutral", ""
            elif marker == "@":
                role = "away" if team == winner else "home"
                venue_team = loser
            else:
                role = "home" if team == winner else "away"
                venue_team = winner
            opponent = loser if team == winner else winner
            candidate = PreviousGame(game_date, role, venue_team, opponent, frozenset((winner, loser)))
            if previous is None or candidate.game_date > previous.game_date:
                previous = candidate
    return previous


def latest_previous_game(games_file: Path, team: str) -> PreviousGame | None:
    return previous_game_before(games_file, team)


def miles(first: dict, second: dict) -> float:
    first_lat, first_lon, second_lat, second_lon = map(
        math.radians, (first["lat"], first["lon"], second["lat"], second["lon"])
    )
    haversine = (
        math.sin((second_lat - first_lat) / 2) ** 2
        + math.cos(first_lat) * math.cos(second_lat) * math.sin((second_lon - first_lon) / 2) ** 2
    )
    return 2 * EARTH_RADIUS_MILES * math.asin(math.sqrt(haversine))


def offset_hours(location: dict, reference_date: date) -> float:
    local_noon = datetime.combine(reference_date, time(12), ZoneInfo(location["timezone"]))
    return local_noon.utcoffset().total_seconds() / 3600


def leg_summary(first: dict, second: dict, reference_date: date) -> dict:
    start_offset = offset_hours(first, reference_date)
    end_offset = offset_hours(second, reference_date)
    return {
        "from": first,
        "to": second,
        "miles": miles(first, second),
        "timezone_transition": abs(end_offset - start_offset),
    }


def print_location(label: str, location: dict, reference_date: date) -> None:
    print(
        f"{label}: {location['city']} ({location['timezone']}, "
        f"UTC{offset_hours(location, reference_date):+.0f})"
    )


def main() -> int:
    args = parse_args()
    team = args.team.strip()
    by_team, by_city, neutral_by_game = load_locations()
    if team not in by_team:
        raise ValueError(f"team not found in location catalog: {team}")
    next_location = by_city.get(normalize(args.next_game_city))
    if next_location is None:
        raise ValueError(f"next game city is not in location catalog: {args.next_game_city}")

    previous = latest_previous_game(args.games_file, team)
    if previous is None:
        print(f"team: {team}")
        print("previous_game: none")
        print("travel_miles: unavailable")
        print("timezone_transition_hours: unavailable")
        return 0

    reference_date = parse_date(args.next_game_date) if args.next_game_date else previous.game_date
    home_location = by_team[team]
    if args.venue == "home" and next_location != home_location:
        raise ValueError(
            f"home game city must resolve to {home_location['city']}, not {next_location['city']}"
        )
    if previous.role == "neutral":
        catalog_city = neutral_by_game.get((previous.game_date.isoformat(), previous.participants))
        previous_location = by_city.get(normalize(catalog_city or args.previous_game_city or ""))
        if previous_location is None:
            raise ValueError(
                "latest previous game was neutral-site; add it to neutral_games or provide --previous-game-city"
            )
    else:
        previous_location = by_team[previous.venue_team]

    if args.venue == "home":
        legs = [] if previous.role == "home" else [leg_summary(previous_location, home_location, reference_date)]
        route = "already_home" if not legs else "previous_venue_to_home"
        destination = home_location
    elif previous.role == "home":
        legs = [leg_summary(home_location, next_location, reference_date)]
        route = "home_to_next_away"
        destination = next_location
    else:
        direct = leg_summary(previous_location, next_location, reference_date)
        via_home = [
            leg_summary(previous_location, home_location, reference_date),
            leg_summary(home_location, next_location, reference_date),
        ]
        if sum(leg["miles"] for leg in via_home) < 2 * direct["miles"]:
            legs, route = via_home, "previous_venue_to_home_to_next_away"
        else:
            legs, route = [direct], "previous_venue_to_next_away"
        destination = next_location

    total_miles = sum(leg["miles"] for leg in legs)
    transition_hours = sum(leg["timezone_transition"] for leg in legs)
    net_change = offset_hours(destination, reference_date) - offset_hours(previous_location, reference_date)
    print(f"team: {team}")
    print(f"previous_game: {previous.game_date.isoformat()} {previous.role} vs {previous.opponent}")
    print_location("previous_city", previous_location, reference_date)
    print_location("next_city", destination, reference_date)
    print(f"route: {route}")
    for index, leg in enumerate(legs, start=1):
        print(f"leg_{index}: {leg['from']['city']} -> {leg['to']['city']} ({round(leg['miles'])} miles)")
    print(f"travel_miles: {round(total_miles)}")
    print(f"timezone_transition_hours: {transition_hours:g}")
    print(f"net_timezone_change_hours: {net_change:+g}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
