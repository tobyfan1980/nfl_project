"""Build the static predictions website from the merged per-game metrics.

Reads dev_data/metrics/{year}_all_game_metrics.csv, scores every game with the
working logistic model (home vs away last-5 win rate gap), and writes a single
self-contained page to docs/index.html for GitHub Pages.

Games in --upcoming-week (and any game without scores) are shown as upcoming
predictions; earlier weeks feed the accuracy section.
"""

import argparse
import csv
import json
import math
import os
from datetime import datetime, timezone

# Logistic fit on 2022-2024 (project_log/2026_09_07.md):
# logit P(home win) = 0.3271 + 1.8526 * (home_last5_win_rate - away_last5_win_rate)
LOGIT_INTERCEPT = 0.3271
LOGIT_SLOPE = 1.8526

TEMPLATE_PATH = os.path.join("web", "template.html")
DATA_PLACEHOLDER = "/*__SITE_DATA__*/null"


def home_win_probability(home_last5_win_rate: float, away_last5_win_rate: float) -> float:
    win_rate_gap = home_last5_win_rate - away_last5_win_rate
    return 1 / (1 + math.exp(-(LOGIT_INTERCEPT + LOGIT_SLOPE * win_rate_gap)))


def parse_score(value: str):
    value = (value or "").strip()
    return int(value) if value else None


def load_games(year: int, upcoming_week: int):
    path = os.path.join("dev_data", "metrics", f"{year}_all_game_metrics.csv")
    games = []
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            week = int(row["week"])
            if upcoming_week and week > upcoming_week:
                continue
            home_last5 = float(row["home_last5_win_rate"])
            away_last5 = float(row["away_last5_win_rate"])
            home_prob = home_win_probability(home_last5, away_last5)
            home_score = parse_score(row["home_score"])
            away_score = parse_score(row["away_score"])
            is_upcoming = week == upcoming_week or home_score is None
            game = {
                "date": row["date"],
                "time": row["time"],
                "week": week,
                "home_team": row["home_team"],
                "away_team": row["away_team"],
                "home_last5": home_last5,
                "away_last5": away_last5,
                "home_prob": round(home_prob, 4),
                "pick": row["home_team"] if home_prob >= 0.5 else row["away_team"],
                "upcoming": is_upcoming,
            }
            if not is_upcoming:
                game["home_score"] = home_score
                game["away_score"] = away_score
                game["winner"] = row["game_winner"]
                game["tie"] = home_score == away_score
                game["correct"] = (not game["tie"]) and game["pick"] == row["game_winner"]
            games.append(game)
    return games


def summarize_accuracy(games):
    scored = [g for g in games if not g["upcoming"] and not g["tie"]]
    weeks = {}
    for g in scored:
        week = weeks.setdefault(g["week"], {"week": g["week"], "games": 0, "correct": 0, "home_wins": 0})
        week["games"] += 1
        week["correct"] += int(g["correct"])
        week["home_wins"] += int(g["winner"] == g["home_team"])
    total = len(scored)
    return {
        "games": total,
        "correct": sum(w["correct"] for w in weeks.values()),
        "home_wins": sum(w["home_wins"] for w in weeks.values()),
        "weeks": [weeks[k] for k in sorted(weeks)],
    }


def main():
    parser = argparse.ArgumentParser(description="Build the static NFL predictions site")
    parser.add_argument("--year", type=int, required=True, help="Season year, e.g. 2025")
    parser.add_argument("--upcoming-week", type=int, default=0,
                        help="Week to show as upcoming predictions (scores hidden); later weeks are dropped")
    parser.add_argument("--output", default=os.path.join("docs", "index.html"))
    args = parser.parse_args()

    games = load_games(args.year, args.upcoming_week)
    upcoming = [g for g in games if g["upcoming"]]
    site_data = {
        "season": args.year,
        "upcoming_week": upcoming[0]["week"] if upcoming else None,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "model": {"intercept": LOGIT_INTERCEPT, "slope": LOGIT_SLOPE},
        "upcoming": upcoming,
        "past": [g for g in games if not g["upcoming"]],
        "accuracy": summarize_accuracy(games),
    }

    with open(TEMPLATE_PATH) as f:
        template = f.read()
    if DATA_PLACEHOLDER not in template:
        raise SystemExit(f"Placeholder {DATA_PLACEHOLDER} not found in {TEMPLATE_PATH}")
    page = template.replace(DATA_PLACEHOLDER, json.dumps(site_data, separators=(",", ":")))

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w") as f:
        f.write(page)

    acc = site_data["accuracy"]
    print(f"Wrote {args.output}")
    print(f"Upcoming games: {len(upcoming)} (week {site_data['upcoming_week']})")
    if acc["games"]:
        print(f"Past accuracy: {acc['correct']}/{acc['games']} = {acc['correct'] / acc['games']:.1%}; "
              f"always-home baseline {acc['home_wins'] / acc['games']:.1%}")


if __name__ == "__main__":
    main()
