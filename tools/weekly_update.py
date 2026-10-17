"""Weekly update: pull results, save next week's picks, rebuild the site.

Run on Tuesday night (Pacific), after Monday Night Football is final:

    python tools/weekly_update.py

Steps:
1. Download the season's schedule and scores from nflverse and save them to
   dev_data/games/{season}_schedule.csv.
2. Find the next week to predict: the first week that still has unplayed
   games, provided every earlier week is final.
3. Predict that week from results in earlier weeks only, and save the picks to
   dev_data/predictions/{season}/week_NN.json. A saved week is never
   overwritten (unless --force), so the site's history is exactly what was
   predicted at the time.
4. Rebuild docs/index.html from the saved picks and the latest scores.

Then review and commit dev_data/ and docs/, and push to publish.
"""

import argparse
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import build_site  # noqa: E402
import nfl_model  # noqa: E402

FIRST_PREDICTED_WEEK = 6  # every team has about five games behind it by then


def predictions_path(season, week):
    return os.path.join("dev_data", "predictions", str(season), f"week_{week:02d}.json")


def next_week_to_predict(games):
    open_weeks = sorted({g["week"] for g in games if not nfl_model.is_final(g)})
    return open_weeks[0] if open_weeks else None


def build_prediction(games, season, week):
    week_games = sorted(
        (g for g in games if g["week"] == week),
        key=lambda g: (g["gameday"], g["gametime"], g["game_id"]),
    )
    already_final = [g["game_id"] for g in week_games if nfl_model.is_final(g)]
    return {
        "season": season,
        "week": week,
        "generated_at": datetime.now(nfl_model.PACIFIC).strftime("%Y-%m-%dT%H:%M%z"),
        "features_through_week": week - 1,
        "model": nfl_model.MODEL,
        "data_source": nfl_model.SCHEDULE_URL,
        "games_final_before_prediction": already_final,
        "games": [nfl_model.predict_game(games, g) for g in week_games],
    }


def main():
    parser = argparse.ArgumentParser(description="Pull results, predict next week, rebuild the site")
    parser.add_argument("--season", type=int, default=2026, help="Season year (default: 2026)")
    parser.add_argument("--week", type=int, help="Week to predict (default: next week with unplayed games)")
    parser.add_argument("--offline", action="store_true", help="Use the saved schedule instead of downloading")
    parser.add_argument("--force", action="store_true", help="Overwrite an existing prediction file")
    args = parser.parse_args()

    path = nfl_model.schedule_path(args.season)
    if args.offline:
        print(f"Using saved schedule {path}")
    else:
        print(f"Downloading {args.season} schedule and scores from nflverse...")
        nfl_model.save_schedule(nfl_model.download_schedule(args.season), path)
        print(f"Saved {path}")
    games = nfl_model.load_schedule(path)
    final = sum(nfl_model.is_final(g) for g in games)
    print(f"{final} of {len(games)} regular-season games are final")

    week = args.week or next_week_to_predict(games)
    if week is None:
        print("Regular season is complete; nothing left to predict.")
    elif week < FIRST_PREDICTED_WEEK:
        print(f"Week {week} is too early for last-5 picks; predictions start in week {FIRST_PREDICTED_WEEK}.")
    else:
        unfinished_earlier = [g["game_id"] for g in games if g["week"] < week and not nfl_model.is_final(g)]
        out = predictions_path(args.season, week)
        if unfinished_earlier:
            print(f"Not predicting week {week}: earlier games are not final yet: {', '.join(unfinished_earlier)}")
            print("Re-run after those scores are posted.")
        elif os.path.exists(out) and not args.force:
            print(f"Week {week} picks already saved at {out}; keeping them (use --force to replace).")
        else:
            prediction = build_prediction(games, args.season, week)
            os.makedirs(os.path.dirname(out), exist_ok=True)
            with open(out, "w", encoding="utf-8") as f:
                json.dump(prediction, f, indent=2)
                f.write("\n")
            print(f"Saved {len(prediction['games'])} week {week} picks to {out}")
            if prediction["games_final_before_prediction"]:
                print("  Warning: these games were already final when predicting: "
                      + ", ".join(prediction["games_final_before_prediction"]))
            for g in prediction["games"]:
                p = g["home_win_prob"]
                print(f"  {g['away']:>3} at {g['home']:<3}  home win {p:.0%}  pick {g['pick']}")

    build_site.build(args.season)


if __name__ == "__main__":
    main()
