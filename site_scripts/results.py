"""PocketPicks results tracking: final scores + whether the stored pick won.

Final scores come from the completed-games CSV (``dev_data/games/{season}_games.csv``).
Columns: ``Week, Day, Date, Time, Winner/tie, <marker>, Loser/tie, ..., PtsW, PtsL``.
The blank-named column holds ``@`` when the winner was the AWAY team; when it
is empty the winner was HOME (same rule as ``calculate_rating_per_game.py``).
"""
import copy
import csv
import json


def _load_games(games_csv_path: str, week: int) -> dict:
    """Map (home_team, away_team) -> (home_pts, away_pts, winner_side) for ``week``.

    Ties (equal points) are omitted: they have no home/away winner, and the
    data contract only allows ``"home"``/``"away"``.
    """
    games = {}
    with open(games_csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                if int(row["Week"]) != week:
                    continue
            except (TypeError, ValueError):
                continue  # playoff rounds etc. have non-numeric weeks
            pts_w, pts_l = int(row["PtsW"]), int(row["PtsL"])
            if pts_w == pts_l:
                continue
            winner, loser = row["Winner/tie"], row["Loser/tie"]
            if any("@" in str(v) for v in row.values() if v is not None):
                home, away, home_pts, away_pts, side = loser, winner, pts_l, pts_w, "away"
            else:
                home, away, home_pts, away_pts, side = winner, loser, pts_w, pts_l, "home"
            games[(home, away)] = (home_pts, away_pts, side)
    return games


def update_results(results: dict, season: int, week: int,
                   games_csv_path: str, week_json_path: str) -> dict:
    """Return ``results`` with this week's finished games added/replaced.

    Games in the week JSON that are not (yet) in the CSV, or that tied, are
    skipped. ``picked`` is the stored ``prediction.favored`` (``None`` when the
    game had no prediction); ``correct`` is ``picked == winner`` or ``None``.
    Keyed by game id, so re-running a week replaces rather than duplicates.
    The input dict is not mutated.
    """
    with open(week_json_path, encoding="utf-8") as f:
        week_data = json.load(f)
    finished = _load_games(games_csv_path, week)

    out = copy.deepcopy(results)
    for game in week_data["games"]:
        hit = finished.get((game["home"]["team"], game["away"]["team"]))
        if hit is None:
            continue
        home_pts, away_pts, winner = hit
        prediction = game.get("prediction")
        picked = prediction["favored"] if prediction else None
        out[game["id"]] = {
            "season": season,
            "week": week,
            "final": f"{home_pts}-{away_pts}",
            "winner": winner,
            "picked": picked,
            "correct": None if picked is None else picked == winner,
        }
    return out
