"""Tests for the nflverse schedule parser (site_scripts/fetch_schedule.py).

Offline only: parse_schedule runs against a saved sample of the real nflverse
games.csv (tests/fixtures/nflverse_sample.csv). fetch_schedule (network) is
not unit-tested. Import path comes from conftest.py.
"""
from pathlib import Path

import pytest

from fetch_schedule import NFLVERSE_TO_FULL, TEAM_SLUGS, parse_schedule

SAMPLE = (Path(__file__).parent / "fixtures" / "nflverse_sample.csv").read_text()


def by_id(games):
    return {g["id"]: g for g in games}


def test_parse_schedule():
    games = parse_schedule(SAMPLE, 2024, 1)
    assert len(games) == 6
    g = by_id(games)

    # Ruling 1: {season}-W{week:02d}-{home_slug}-{away_slug}, lowercase, home first
    assert set(g) == {
        "2024-W01-kc-bal",
        "2024-W01-phi-gb",
        "2024-W01-atl-pit",
        "2024-W01-tb-wsh",
        "2024-W01-det-lar",
        "2024-W01-sf-nyj",
    }

    # Full matchup record; nflverse columns are away_team / home_team
    assert g["2024-W01-kc-bal"] == {
        "id": "2024-W01-kc-bal",
        "kickoff_utc": "2024-09-06T00:20:00Z",  # Thu 20:20 EDT -> crosses midnight UTC
        "home_team": "Kansas City Chiefs",
        "home_slug": "kc",
        "away_team": "Baltimore Ravens",
        "away_slug": "bal",
    }
    # Code mapping: WAS -> Washington Commanders/wsh, LA -> Los Angeles Rams/lar
    assert g["2024-W01-tb-wsh"]["away_team"] == "Washington Commanders"
    assert g["2024-W01-det-lar"]["away_team"] == "Los Angeles Rams"
    assert g["2024-W01-det-lar"]["home_team"] == "Detroit Lions"

    # Eastern -> UTC, EDT (UTC-4) in September
    assert g["2024-W01-atl-pit"]["kickoff_utc"] == "2024-09-08T17:00:00Z"
    assert g["2024-W01-tb-wsh"]["kickoff_utc"] == "2024-09-08T20:25:00Z"
    assert g["2024-W01-sf-nyj"]["kickoff_utc"] == "2024-09-10T00:15:00Z"


def test_parse_schedule_filters_by_season_and_week():
    assert len(parse_schedule(SAMPLE, 2024, 2)) == 2
    assert parse_schedule(SAMPLE, 2024, 3) == []
    assert parse_schedule(SAMPLE, 2023, 1) == []


def test_parse_schedule_dst_aware():
    """After the first Sunday of November Eastern is EST (UTC-5)."""
    g = by_id(parse_schedule(SAMPLE, 2024, 10))
    assert g["2024-W10-bal-cin"]["kickoff_utc"] == "2024-11-08T01:15:00Z"  # Thu 20:15 EST
    assert g["2024-W10-kc-den"]["kickoff_utc"] == "2024-11-10T18:00:00Z"  # 13:00 EST
    assert g["2024-W10-car-nyg"]["kickoff_utc"] == "2024-11-10T14:30:00Z"  # 09:30 EST (Munich)
    assert g["2024-W10-wsh-pit"]["home_team"] == "Washington Commanders"


def test_kickoff_format_matches_contract():
    import re

    for gm in parse_schedule(SAMPLE, 2024, 10):
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", gm["kickoff_utc"])


def test_team_maps_cover_all_32_teams():
    assert len(NFLVERSE_TO_FULL) >= 32
    full_names = set(NFLVERSE_TO_FULL.values())
    assert len(full_names) == 32
    assert set(TEAM_SLUGS) == full_names
    slugs = list(TEAM_SLUGS.values())
    assert len(set(slugs)) == 32
    assert all(s == s.lower() and s.isalpha() for s in slugs)
    assert TEAM_SLUGS["Kansas City Chiefs"] == "kc"
    assert TEAM_SLUGS["Washington Commanders"] == "wsh"


def test_unknown_team_code_raises():
    bad = "season,week,gameday,gametime,away_team,home_team\n2024,1,2024-09-05,20:20,XXX,KC\n"
    with pytest.raises(KeyError):
        parse_schedule(bad, 2024, 1)
