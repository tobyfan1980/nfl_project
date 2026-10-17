"""Build dev_data/metrics/{year}_all_game_metrics.csv from the per-season CSVs.

Joins the season games file with the intervals, travel-timezone, win-rate and
opponent-strength tables on (date, team), one row per regular-season game from
week 6 on. Home/away comes from the games file venue marker: blank means the
winner was home, "@" means the winner was away, and "N" (neutral site) is
resolved with the travel-timezone `team_role` column.

Example:
    python tools/merge_all_game_metrics.py --year 2025
"""

import argparse
import csv
import os

REST_ORDER = {"limited rest": 0, "regular rest": 1, "more rest": 2, "excessive rest": 3}

OUTPUT_COLUMNS = [
    "date", "time", "week", "home_team", "away_team", "home_score", "away_score",
    "home_travel_or_not", "away_travel_or_not", "home_travel_miles_log", "away_travel_miles_log",
    "home_rest_period", "away_rest_period", "rest_period_diff",
    "home_timezone_difference", "away_timezone_difference",
    "home_last5_win_rate", "away_last5_win_rate",
    "home_opponent_last5_win_rate", "away_opponent_last5_win_rate",
    "game_condition", "game_winner", "game_loser", "game_temperature",
]


def read_keyed(path):
    """Index a metrics CSV by (date, team)."""
    with open(path, newline="", encoding="utf-8") as f:
        return {(row["date"], row["team"]): row for row in csv.DictReader(f)}


def read_games(path):
    """Yield regular-season games from the 17-column season games CSV."""
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader)
        for row in reader:
            if len(row) < 10 or not row[0].strip().isdigit():
                continue
            row = row + [""] * (17 - len(row))
            yield {
                "week": int(row[0]),
                "date": row[2],
                "time": row[3],
                "winner": row[4],
                "marker": row[5].strip(),
                "loser": row[6],
                "winner_score": row[8],
                "loser_score": row[9],
                "temperature": row[15],
                "condition": row[16],
            }


def rest_period_diff(home_rest, away_rest):
    if home_rest not in REST_ORDER or away_rest not in REST_ORDER:
        return ""
    if REST_ORDER[home_rest] < REST_ORDER[away_rest]:
        return "home team rest less"
    if REST_ORDER[home_rest] > REST_ORDER[away_rest]:
        return "home team rest more"
    return "home team rest same"


def winner_is_home(game, travel):
    if game["marker"] == "@":
        return False
    if game["marker"] == "N":
        return travel.get((game["date"], game["winner"]), {}).get("team_role") == "home"
    return True


def build_rows(year, first_week):
    metrics_dir = os.path.join("dev_data", "metrics")
    intervals = read_keyed(os.path.join(metrics_dir, f"{year}_game_intervals.csv"))
    travel = read_keyed(os.path.join(metrics_dir, f"{year}_travel-timezone.csv"))
    win_rate = read_keyed(os.path.join(metrics_dir, f"{year}_win_rate.csv"))
    opp_strength = read_keyed(os.path.join(metrics_dir, f"{year}_opp_strength.csv"))

    rows = []
    for game in read_games(os.path.join("dev_data", "games", f"{year}_games.csv")):
        if game["week"] < first_week:
            continue
        if winner_is_home(game, travel):
            home, away = game["winner"], game["loser"]
            home_score, away_score = game["winner_score"], game["loser_score"]
        else:
            home, away = game["loser"], game["winner"]
            home_score, away_score = game["loser_score"], game["winner_score"]
        date = game["date"]
        # A team missing from a metrics table (e.g. a gap in the source data)
        # leaves that table's columns blank instead of failing the season.
        home_interval, away_interval = intervals.get((date, home), {}), intervals.get((date, away), {})
        home_travel, away_travel = travel.get((date, home), {}), travel.get((date, away), {})
        home_rate, away_rate = win_rate.get((date, home), {}), win_rate.get((date, away), {})
        home_opp, away_opp = opp_strength.get((date, home), {}), opp_strength.get((date, away), {})
        home_rest = home_interval.get("rest_period", "")
        away_rest = away_interval.get("rest_period", "")
        rows.append({
            "date": date,
            "time": game["time"],
            "week": game["week"],
            "home_team": home,
            "away_team": away,
            "home_score": home_score,
            "away_score": away_score,
            "home_travel_or_not": home_travel.get("travel_or_not", ""),
            "away_travel_or_not": away_travel.get("travel_or_not", ""),
            "home_travel_miles_log": home_travel.get("travel_miles_log", ""),
            "away_travel_miles_log": away_travel.get("travel_miles_log", ""),
            "home_rest_period": home_rest,
            "away_rest_period": away_rest,
            "rest_period_diff": rest_period_diff(home_rest, away_rest),
            "home_timezone_difference": home_travel.get("timezone_difference", ""),
            "away_timezone_difference": away_travel.get("timezone_difference", ""),
            "home_last5_win_rate": home_rate.get("win_rate", ""),
            "away_last5_win_rate": away_rate.get("win_rate", ""),
            "home_opponent_last5_win_rate": home_opp.get("opponent_strength_average_win_rate", ""),
            "away_opponent_last5_win_rate": away_opp.get("opponent_strength_average_win_rate", ""),
            "game_condition": game["condition"],
            "game_winner": game["winner"],
            "game_loser": game["loser"],
            "game_temperature": game["temperature"],
        })
    return rows


def main():
    parser = argparse.ArgumentParser(description="Merge per-game metrics into one table per season")
    parser.add_argument("--year", type=int, required=True, help="Season year, e.g. 2025")
    parser.add_argument("--first-week", type=int, default=6, help="First week to include (default: 6)")
    parser.add_argument("--output", help="Output CSV (default: dev_data/metrics/{year}_all_game_metrics.csv)")
    args = parser.parse_args()

    output = args.output or os.path.join("dev_data", "metrics", f"{args.year}_all_game_metrics.csv")
    rows = build_rows(args.year, args.first_week)
    with open(output, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} games to {output}")


if __name__ == "__main__":
    main()
