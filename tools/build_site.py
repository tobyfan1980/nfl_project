"""Build the static predictions site (docs/index.html) for GitHub Pages.

Reads the saved weekly picks in dev_data/predictions/{season}/week_NN.json and
the latest scores in dev_data/games/{season}_schedule.csv. Past picks are read
from the saved files only, never recomputed, so the record on the site is what
was actually predicted before each week.

Usually run through tools/weekly_update.py; on its own:
    python tools/build_site.py --season 2026
"""

import argparse
import glob
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import nfl_model  # noqa: E402

TEMPLATE_PATH = os.path.join("web", "template.html")
OUTPUT_PATH = os.path.join("docs", "index.html")
DATA_PLACEHOLDER = "/*__SITE_DATA__*/null"

# 2025 hold-out test of the same model (project_log/2026_09_07.md)
BACKTEST = {"season": 2025, "games": 194, "correct": 135, "home_wins": 103}

# abbreviation: (city, nickname, primary color, chip text color)
TEAMS = {
    "ARI": ("Arizona", "Cardinals", "#97233F", "#fff"),
    "ATL": ("Atlanta", "Falcons", "#A71930", "#fff"),
    "BAL": ("Baltimore", "Ravens", "#241773", "#fff"),
    "BUF": ("Buffalo", "Bills", "#00338D", "#fff"),
    "CAR": ("Carolina", "Panthers", "#0085CA", "#fff"),
    "CHI": ("Chicago", "Bears", "#0B162A", "#fff"),
    "CIN": ("Cincinnati", "Bengals", "#FB4F14", "#111"),
    "CLE": ("Cleveland", "Browns", "#311D00", "#fff"),
    "DAL": ("Dallas", "Cowboys", "#003594", "#fff"),
    "DEN": ("Denver", "Broncos", "#FB4F14", "#111"),
    "DET": ("Detroit", "Lions", "#0076B6", "#fff"),
    "GB": ("Green Bay", "Packers", "#203731", "#fff"),
    "HOU": ("Houston", "Texans", "#03202F", "#fff"),
    "IND": ("Indianapolis", "Colts", "#002C5F", "#fff"),
    "JAX": ("Jacksonville", "Jaguars", "#006778", "#fff"),
    "KC": ("Kansas City", "Chiefs", "#E31837", "#fff"),
    "LV": ("Las Vegas", "Raiders", "#000000", "#fff"),
    "LAC": ("Los Angeles", "Chargers", "#0080C6", "#fff"),
    "LA": ("Los Angeles", "Rams", "#003594", "#fff"),
    "MIA": ("Miami", "Dolphins", "#008E97", "#fff"),
    "MIN": ("Minnesota", "Vikings", "#4F2683", "#fff"),
    "NE": ("New England", "Patriots", "#002244", "#fff"),
    "NO": ("New Orleans", "Saints", "#D3BC8D", "#111"),
    "NYG": ("New York", "Giants", "#0B2265", "#fff"),
    "NYJ": ("New York", "Jets", "#125740", "#fff"),
    "PHI": ("Philadelphia", "Eagles", "#004C54", "#fff"),
    "PIT": ("Pittsburgh", "Steelers", "#FFB612", "#111"),
    "SF": ("San Francisco", "49ers", "#AA0000", "#fff"),
    "SEA": ("Seattle", "Seahawks", "#002244", "#fff"),
    "TB": ("Tampa Bay", "Buccaneers", "#D50A0A", "#fff"),
    "TEN": ("Tennessee", "Titans", "#4B92DB", "#111"),
    "WAS": ("Washington", "Commanders", "#5A1414", "#fff"),
}


def load_predictions(season):
    pattern = os.path.join("dev_data", "predictions", str(season), "week_*.json")
    weeks = []
    for path in sorted(glob.glob(pattern)):
        with open(path, encoding="utf-8") as f:
            weeks.append(json.load(f))
    return sorted(weeks, key=lambda w: w["week"])


def grade(pick, game):
    """Attach the final score and hit/miss to a saved pick."""
    graded = dict(pick)
    if game is None or not nfl_model.is_final(game):
        graded["status"] = "upcoming"
        return graded
    graded["status"] = "final"
    graded["home_score"] = game["home_score"]
    graded["away_score"] = game["away_score"]
    if game["home_score"] == game["away_score"]:
        graded["result"] = "tie"
    else:
        winner = game["home_team"] if game["home_score"] > game["away_score"] else game["away_team"]
        graded["winner"] = winner
        graded["result"] = "hit" if pick["pick"] == winner else "miss"
    return graded


def summarize(weeks):
    summary = {"decided": 0, "correct": 0, "home_wins": 0, "ties": 0, "pending": 0, "weeks": []}
    for week in weeks:
        row = {"week": week["week"], "decided": 0, "correct": 0, "home_wins": 0}
        for g in week["games"]:
            if g["status"] != "final":
                summary["pending"] += 1
            elif g["result"] == "tie":
                summary["ties"] += 1
            else:
                row["decided"] += 1
                row["correct"] += g["result"] == "hit"
                row["home_wins"] += g["winner"] == g["home"]
        for key in ("decided", "correct", "home_wins"):
            summary[key] += row[key]
        summary["weeks"].append(row)
    return summary


def build(season, output=OUTPUT_PATH):
    schedule = {g["game_id"]: g for g in nfl_model.load_schedule(nfl_model.schedule_path(season))}
    weeks = []
    for saved in load_predictions(season):
        weeks.append({
            "week": saved["week"],
            "generated_at": saved["generated_at"],
            "features_through_week": saved["features_through_week"],
            "games_final_before_prediction": saved.get("games_final_before_prediction", []),
            "games": [grade(p, schedule.get(p["game_id"])) for p in saved["games"]],
        })

    site_data = {
        "season": season,
        "updated": datetime.now(nfl_model.PACIFIC).strftime("%Y-%m-%dT%H:%M%z"),
        "current_week": weeks[-1]["week"] if weeks else None,
        "model": nfl_model.MODEL,
        "backtest": BACKTEST,
        "teams": {abbr: {"city": c, "name": n, "color": col, "ink": ink} for abbr, (c, n, col, ink) in TEAMS.items()},
        "weeks": weeks,
        "record": summarize(weeks),
    }

    with open(TEMPLATE_PATH, encoding="utf-8") as f:
        template = f.read()
    if DATA_PLACEHOLDER not in template:
        raise SystemExit(f"Placeholder {DATA_PLACEHOLDER} not found in {TEMPLATE_PATH}")
    # Escape "</" so team or note text can never close the inline <script>.
    payload = json.dumps(site_data, separators=(",", ":")).replace("</", "<\\/")
    page = template.replace(DATA_PLACEHOLDER, payload)

    os.makedirs(os.path.dirname(output), exist_ok=True)
    with open(output, "w", encoding="utf-8") as f:
        f.write(page)

    record = site_data["record"]
    print(f"Wrote {output}: {len(weeks)} predicted week(s), current week {site_data['current_week']}")
    if record["decided"]:
        print(f"Season record: {record['correct']}-{record['decided'] - record['correct']} "
              f"({record['correct'] / record['decided']:.1%}), {record['pending']} game(s) pending")


def main():
    parser = argparse.ArgumentParser(description="Build the static NFL predictions site")
    parser.add_argument("--season", type=int, default=2026, help="Season year (default: 2026)")
    parser.add_argument("--output", default=OUTPUT_PATH)
    args = parser.parse_args()
    build(args.season, args.output)


if __name__ == "__main__":
    main()
