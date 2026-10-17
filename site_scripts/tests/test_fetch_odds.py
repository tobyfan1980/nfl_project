"""Tests for the odds fetcher (site_scripts/fetch_odds.py).

Offline only: aggregate_odds runs against a saved the-odds-api sample
(tests/fixtures/odds_sample.json); the network GET in fetch_odds is not
unit-tested, only its no-key path. Import path comes from conftest.py.
"""
import json
from pathlib import Path

import fetch_odds
from fetch_odds import aggregate_odds

SAMPLE = json.loads((Path(__file__).parent / "fixtures" / "odds_sample.json").read_text())
HOME, AWAY = "Kansas City Chiefs", "Baltimore Ravens"


def test_aggregate_odds_median():
    odds = aggregate_odds(SAMPLE, HOME, AWAY)
    # home prices -145/-160/-150 -> -150; away 125/130/120 -> 125
    assert odds["home_moneyline"] == -150
    assert odds["away_moneyline"] == 125
    assert odds["books"] == 3
    assert odds["source"] == "the-odds-api"
    assert odds["pulled_at"].endswith("Z")


def test_aggregate_odds_no_matching_event():
    assert aggregate_odds(SAMPLE, "Buffalo Bills", "Miami Dolphins") is None
    assert aggregate_odds([], HOME, AWAY) is None


def test_aggregate_odds_tolerant_team_names():
    # nickname-only / different case still matches the same event
    assert aggregate_odds(SAMPLE, "chiefs", "RAVENS")["books"] == 3


def test_aggregate_odds_even_book_count_rounds_to_int():
    event = json.loads(json.dumps(SAMPLE[0]))
    event["bookmakers"] = event["bookmakers"][:2]  # home -145/-160, away 125/130
    odds = aggregate_odds([event], HOME, AWAY)
    assert odds["books"] == 2
    assert isinstance(odds["home_moneyline"], int)
    assert isinstance(odds["away_moneyline"], int)


def test_aggregate_odds_skips_books_without_h2h():
    event = json.loads(json.dumps(SAMPLE[0]))
    event["bookmakers"][0]["markets"] = [{"key": "spreads", "outcomes": []}]
    odds = aggregate_odds([event], HOME, AWAY)
    assert odds["books"] == 2


def test_aggregate_odds_no_usable_books():
    event = json.loads(json.dumps(SAMPLE[0]))
    event["bookmakers"] = []
    assert aggregate_odds([event], HOME, AWAY) is None


def test_fetch_odds_no_key(monkeypatch, tmp_path):
    monkeypatch.setattr(fetch_odds, "KEY_PATH", tmp_path / "missing_key")
    games = [{"id": "2026-W06-kc-bal", "home_team": HOME, "away_team": AWAY}]
    assert fetch_odds.fetch_odds(games) == {}
