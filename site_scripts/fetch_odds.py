"""PocketPicks odds fetcher: consensus moneylines from the-odds-api.com (free tier).

For each upcoming game the h2h (moneyline) price of every US bookmaker is
collected and the MEDIAN per side is reported, with ``books`` = number of
bookmakers that quoted both sides. The API key lives outside the repo in
``~/.pocketpicks_odds_key``; if that file is absent the fetcher logs a notice
and returns ``{}`` (odds are optional: ``Game.odds`` is ``null``).

Team identity reuses fetch_schedule's maps. Names are compared by slug, so
"Los Angeles Rams" / "Rams" / "rams" all resolve to the same team.
"""
from __future__ import annotations

import logging
import re
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import requests

from fetch_schedule import TEAM_SLUGS

log = logging.getLogger(__name__)

ODDS_URL = "https://api.the-odds-api.com/v4/sports/americanfootball_nfl/odds/"
KEY_PATH = Path.home() / ".pocketpicks_odds_key"
SOURCE = "the-odds-api"

# Lookup of normalized full name / nickname -> slug, built from the schedule's
# team map (e.g. "kansas city chiefs" and "chiefs" -> "kc").
_ALIASES: dict = {}
for _full, _slug in TEAM_SLUGS.items():
    _ALIASES[re.sub(r"[^a-z0-9]", "", _full.lower())] = _slug
    _ALIASES[re.sub(r"[^a-z0-9]", "", _full.split()[-1].lower())] = _slug


def _team_key(name: str) -> str:
    """Canonical key for a team name: its slug if recognised, else the normalized text."""
    norm = re.sub(r"[^a-z0-9]", "", (name or "").lower())
    return _ALIASES.get(norm, norm)


def _book_prices(event: dict, home_key: str, away_key: str):
    """Yield (home_price, away_price) for each bookmaker with a usable h2h market."""
    for book in event.get("bookmakers") or []:
        for market in book.get("markets") or []:
            if market.get("key") != "h2h":
                continue
            prices = {}
            for outcome in market.get("outcomes") or []:
                price = outcome.get("price")
                if isinstance(price, bool) or not isinstance(price, (int, float)):
                    continue
                prices[_team_key(outcome.get("name"))] = price
            if home_key in prices and away_key in prices:
                yield prices[home_key], prices[away_key]
            break  # one h2h market per bookmaker


def _median_moneyline(prices) -> int:
    """Median American price, rounded to a whole line and kept out of the -99..+99 band.

    The median of an even number of books straddling pick'em (e.g. -110 and +120 -> +5)
    is not a valid American price. Snap it to the nearest valid line, resolving the
    tie-free split by sign: 0..99 -> +100, -99..-1 -> -100.
    """
    value = int(round(statistics.median(prices)))
    if -100 < value < 100:
        return 100 if value >= 0 else -100
    return value


def aggregate_odds(api_response: list, home_team: str, away_team: str) -> Optional[dict]:
    """Median moneyline per side across bookmakers for the event matching these teams.

    Returns ``{"home_moneyline", "away_moneyline", "books", "source", "pulled_at"}``
    or None when no event matches or no bookmaker quoted both sides. Prices are
    reported for *our* home/away even if the API lists the teams the other way
    round. With an even number of books the median is rounded to a whole line, and a
    median that lands in the invalid -99..+99 band is snapped to -100/+100.
    """
    home_key, away_key = _team_key(home_team), _team_key(away_team)
    for event in api_response or []:
        if {_team_key(event.get("home_team")), _team_key(event.get("away_team"))} != {home_key, away_key}:
            continue
        pairs = list(_book_prices(event, home_key, away_key))
        if not pairs:
            return None
        return {
            "home_moneyline": _median_moneyline(p[0] for p in pairs),
            "away_moneyline": _median_moneyline(p[1] for p in pairs),
            "books": len(pairs),
            "source": SOURCE,
            "pulled_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
    return None


def _read_key() -> Optional[str]:
    try:
        key = KEY_PATH.read_text().strip()
    except OSError:
        return None
    return key or None


def fetch_odds(games: list) -> dict:
    """Fetch consensus odds for ``games`` -> ``{game_id: Odds}`` (games without a line are omitted).

    Returns ``{}`` (never raises) when the key file is absent or the API call fails.
    """
    key = _read_key()
    if key is None:
        log.warning("odds: no API key at %s; skipping odds", KEY_PATH)
        return {}
    try:
        resp = requests.get(
            ODDS_URL,
            params={"regions": "us", "markets": "h2h", "oddsFormat": "american", "apiKey": key},
            timeout=30,
        )
        resp.raise_for_status()
        events = resp.json()
    except (requests.RequestException, ValueError) as exc:
        # Don't log str(exc): requests embeds the URL, which carries the key.
        log.warning("odds: API request failed (%s); skipping odds", type(exc).__name__)
        return {}
    if not isinstance(events, list):
        # e.g. an error object returned with HTTP 200
        log.warning("odds: unexpected API response shape (%s); skipping odds", type(events).__name__)
        return {}
    result = {}
    for game in games:
        odds = aggregate_odds(events, game["home_team"], game["away_team"])
        if odds is not None:
            result[game["id"]] = odds
    return result
