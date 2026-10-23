"""PocketPicks schedule fetcher: upcoming matchups + kickoff times from nflverse.

The PFR crawler only parses completed box scores, so the schedule comes from
the public nflverse games.csv instead. This module is also the single source of
truth for team identity in the pipeline (nflverse code -> full name -> slug).

Timezone assumption: nflverse ``gametime`` is US Eastern wall-clock time
(``HH:MM``, 24h) on the ``gameday`` date, including international games (a
09:30 Munich kickoff is listed as 09:30 Eastern). Eastern is converted to UTC
with ``zoneinfo.ZoneInfo("America/New_York")`` so EDT (UTC-4) vs EST (UTC-5)
is handled by the tz database rather than a hard-coded offset.
"""
import csv
import io
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

NFLVERSE_GAMES_URL = "https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv"
EASTERN = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")

log = logging.getLogger(__name__)

# nflverse team code -> full team name (as used in dev_data/games/*.csv).
NFLVERSE_TO_FULL = {
    "ARI": "Arizona Cardinals",
    "ATL": "Atlanta Falcons",
    "BAL": "Baltimore Ravens",
    "BUF": "Buffalo Bills",
    "CAR": "Carolina Panthers",
    "CHI": "Chicago Bears",
    "CIN": "Cincinnati Bengals",
    "CLE": "Cleveland Browns",
    "DAL": "Dallas Cowboys",
    "DEN": "Denver Broncos",
    "DET": "Detroit Lions",
    "GB": "Green Bay Packers",
    "HOU": "Houston Texans",
    "IND": "Indianapolis Colts",
    "JAX": "Jacksonville Jaguars",
    "KC": "Kansas City Chiefs",
    "LA": "Los Angeles Rams",  # nflverse games.csv uses LA for the Rams
    "LAC": "Los Angeles Chargers",
    "LV": "Las Vegas Raiders",
    "MIA": "Miami Dolphins",
    "MIN": "Minnesota Vikings",
    "NE": "New England Patriots",
    "NO": "New Orleans Saints",
    "NYG": "New York Giants",
    "NYJ": "New York Jets",
    "PHI": "Philadelphia Eagles",
    "PIT": "Pittsburgh Steelers",
    "SEA": "Seattle Seahawks",
    "SF": "San Francisco 49ers",
    "TB": "Tampa Bay Buccaneers",
    "TEN": "Tennessee Titans",
    "WAS": "Washington Commanders",
    # Aliases other nflverse datasets use for the same franchises.
    "LAR": "Los Angeles Rams",
    "WSH": "Washington Commanders",
}

# Full team name -> lowercase slug (matches site/data fixtures, e.g. "kc", "wsh").
TEAM_SLUGS = {
    "Arizona Cardinals": "ari",
    "Atlanta Falcons": "atl",
    "Baltimore Ravens": "bal",
    "Buffalo Bills": "buf",
    "Carolina Panthers": "car",
    "Chicago Bears": "chi",
    "Cincinnati Bengals": "cin",
    "Cleveland Browns": "cle",
    "Dallas Cowboys": "dal",
    "Denver Broncos": "den",
    "Detroit Lions": "det",
    "Green Bay Packers": "gb",
    "Houston Texans": "hou",
    "Indianapolis Colts": "ind",
    "Jacksonville Jaguars": "jax",
    "Kansas City Chiefs": "kc",
    "Las Vegas Raiders": "lv",
    "Los Angeles Chargers": "lac",
    "Los Angeles Rams": "lar",
    "Miami Dolphins": "mia",
    "Minnesota Vikings": "min",
    "New England Patriots": "ne",
    "New Orleans Saints": "no",
    "New York Giants": "nyg",
    "New York Jets": "nyj",
    "Philadelphia Eagles": "phi",
    "Pittsburgh Steelers": "pit",
    "San Francisco 49ers": "sf",
    "Seattle Seahawks": "sea",
    "Tampa Bay Buccaneers": "tb",
    "Tennessee Titans": "ten",
    "Washington Commanders": "wsh",
}


def _kickoff_utc(gameday: str, gametime: str) -> str:
    """Eastern wall-clock gameday ('YYYY-MM-DD') + gametime ('HH:MM') -> ISO UTC 'Z'."""
    local = datetime.strptime(f"{gameday} {gametime}", "%Y-%m-%d %H:%M").replace(tzinfo=EASTERN)
    return local.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_schedule(csv_text: str, season: int, week: int,
                   skip_unscheduled: bool = False) -> list[dict]:
    """Parse nflverse games.csv text into the Game rows for one (season, week).

    Id format (data contract): ``{season}-W{week:02d}-{home_slug}-{away_slug}``.
    Raises KeyError for an unknown team code and ValueError for a game with no
    kickoff time, rather than silently emitting a bad row. With
    ``skip_unscheduled=True`` a game with no kickoff time (TBD/flexed) is
    logged and left out instead, so one unscheduled game cannot abort the whole
    week; it appears on a later run once nflverse lists its time.
    """
    games = []
    for row in csv.DictReader(io.StringIO(csv_text)):
        if int(row["season"]) != season or int(row["week"]) != week:
            continue
        home_team = NFLVERSE_TO_FULL[row["home_team"]]
        away_team = NFLVERSE_TO_FULL[row["away_team"]]
        home_slug = TEAM_SLUGS[home_team]
        away_slug = TEAM_SLUGS[away_team]
        if not row.get("gameday") or not row.get("gametime"):
            if skip_unscheduled:
                log.warning("schedule: skipping %s (no kickoff time yet)",
                            row.get("game_id") or f"{away_team} at {home_team}")
                continue
            raise ValueError(f"no kickoff time for {row.get('game_id') or row}")
        games.append(
            {
                "id": f"{season}-W{week:02d}-{home_slug}-{away_slug}",
                "kickoff_utc": _kickoff_utc(row["gameday"], row["gametime"]),
                "home_team": home_team,
                "home_slug": home_slug,
                "away_team": away_team,
                "away_slug": away_slug,
            }
        )
    return games


def fetch_schedule(season: int, week: int, skip_unscheduled: bool = False) -> list[dict]:
    """Download the nflverse games.csv and return that week's games."""
    resp = requests.get(NFLVERSE_GAMES_URL, timeout=30)
    resp.raise_for_status()
    return parse_schedule(resp.text, season, week, skip_unscheduled)
