"""Shared pieces of the weekly prediction pipeline.

- Schedule and scores come from the nflverse games table (free, updated within
  hours of each game, and it includes the upcoming schedule we need to predict).
- Features follow plugins/nfl-previous-five-win-rate: a team's win rate over its
  last five games of the season before the game, ties count as half a win.
- The model is the logistic fit from project_log/2026_09_07.md (2022-2024).
"""

import csv
import io
import math
import os
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

SCHEDULE_URL = "https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv"
USER_AGENT = "Mozilla/5.0 (compatible; NFLProjectPredictor/1.0)"

# logit P(home win) = 0.3271 + 1.8526 * (home_last5_win_rate - away_last5_win_rate)
MODEL = {
    "name": "last5-logistic-v1",
    "intercept": 0.3271,
    "slope": 1.8526,
    "trained_on": "2022-2024 regular season, weeks 6-18",
}
WINDOW = 5

SCHEDULE_COLUMNS = [
    "game_id", "season", "game_type", "week", "gameday", "weekday", "gametime",
    "away_team", "away_score", "home_team", "home_score", "location",
]

EASTERN = ZoneInfo("America/New_York")
PACIFIC = ZoneInfo("America/Los_Angeles")


def schedule_path(season):
    return os.path.join("dev_data", "games", f"{season}_schedule.csv")


def download_schedule(season):
    """Fetch this season's regular-season rows from nflverse."""
    request = urllib.request.Request(SCHEDULE_URL, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        text = response.read().decode("utf-8")
    rows = [
        {column: row[column] for column in SCHEDULE_COLUMNS}
        for row in csv.DictReader(io.StringIO(text))
        if row["season"] == str(season) and row["game_type"] == "REG"
    ]
    if not rows:
        raise RuntimeError(f"nflverse has no {season} regular-season games yet")
    return rows


def save_schedule(rows, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=SCHEDULE_COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def load_schedule(path):
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for row in rows:
        row["week"] = int(row["week"])
        row["away_score"] = int(row["away_score"]) if row["away_score"] else None
        row["home_score"] = int(row["home_score"]) if row["home_score"] else None
    return rows


def is_final(game):
    return game["home_score"] is not None and game["away_score"] is not None


def kickoff_pacific(game):
    """nflverse kickoff times are US Eastern; the site shows Pacific."""
    eastern = datetime.strptime(f"{game['gameday']} {game['gametime']}", "%Y-%m-%d %H:%M")
    return eastern.replace(tzinfo=EASTERN).astimezone(PACIFIC)


def last5_record(games, team, before_week):
    """Win rate over the team's last five final games in weeks before `before_week`."""
    team_games = [
        g for g in games
        if g["week"] < before_week and is_final(g) and team in (g["home_team"], g["away_team"])
    ]
    team_games.sort(key=lambda g: (g["gameday"], g["gametime"]))
    recent = team_games[-WINDOW:]
    wins = losses = ties = 0
    for g in recent:
        own, other = (g["home_score"], g["away_score"]) if g["home_team"] == team else (g["away_score"], g["home_score"])
        if own > other:
            wins += 1
        elif own < other:
            losses += 1
        else:
            ties += 1
    played = len(recent)
    rate = round((wins + 0.5 * ties) / played, 3) if played else 0.0
    return {"games": played, "wins": wins, "losses": losses, "ties": ties, "win_rate": rate}


def home_win_probability(home_rate, away_rate):
    x = home_rate - away_rate
    return 1 / (1 + math.exp(-(MODEL["intercept"] + MODEL["slope"] * x)))


def predict_game(games, game):
    """Pick for one game, using only results from earlier weeks."""
    home = last5_record(games, game["home_team"], game["week"])
    away = last5_record(games, game["away_team"], game["week"])
    prob = home_win_probability(home["win_rate"], away["win_rate"])
    pick = game["home_team"] if prob >= 0.5 else game["away_team"]
    return {
        "game_id": game["game_id"],
        "kickoff_pt": kickoff_pacific(game).strftime("%Y-%m-%dT%H:%M%z"),
        "location": game["location"],
        "home": game["home_team"],
        "away": game["away_team"],
        "home_last5": home,
        "away_last5": away,
        "home_win_prob": round(prob, 4),
        "pick": pick,
    }
