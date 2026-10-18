"""PocketPicks results tracking: final scores + whether the stored pick won.

Final scores come from the completed-games CSV (``dev_data/games/{season}_games.csv``).
Columns: ``Week, Day, Date, Time, Winner/tie, <marker>, Loser/tie, ..., PtsW, PtsL``.
The ``@`` marker is deliberately NOT used: home/away for each game is taken
from the week JSON (nflverse), which can disagree with PFR on neutral sites.
"""
import copy
import csv
import json
import logging

log = logging.getLogger(__name__)


def _load_games(games_csv_path: str, week: int) -> dict:
    """Map frozenset({winner, loser}) -> finished-game info for ``week``.

    Keyed by the unordered team pair and storing the winner by TEAM, so scoring
    does not depend on which source (PFR ``@`` marker vs nflverse) labelled
    home/away; they disagree for neutral-site games. Ties (equal points) are
    omitted: they have no winner, and the data contract only allows
    ``"home"``/``"away"``.
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
            games[frozenset((winner, loser))] = {
                "winner_team": winner, "loser_team": loser,
                "winner_pts": pts_w, "loser_pts": pts_l,
            }
    return games


def update_results(results: dict, season: int, week: int,
                   games_csv_path: str, week_json_path: str) -> dict:
    """Return ``results`` with this week's finished games added/replaced.

    Games in the week JSON that are not (yet) in the CSV, or that tied, are
    skipped (with a logged warning, so team-name drift between sources shows up). ``picked`` is the stored ``prediction.favored`` (``None`` when the
    game had no prediction); ``correct`` is ``picked == winner`` or ``None``.
    Keyed by game id, so re-running a week replaces rather than duplicates.
    The input dict is not mutated.
    """
    with open(week_json_path, encoding="utf-8") as f:
        week_data = json.load(f)
    finished = _load_games(games_csv_path, week)

    out = copy.deepcopy(results)
    for game in week_data["games"]:
        home_team, away_team = game["home"]["team"], game["away"]["team"]
        hit = finished.get(frozenset((home_team, away_team)))
        if hit is None:
            # Normal for unplayed games and ties; but also the symptom of a team
            # spelling drift between nflverse and PFR, so keep it visible.
            log.warning(
                "results: game %s (%s vs %s) not found among finished week %d games; not scored",
                game["id"], home_team, away_team, week,
            )
            continue
        home_won = hit["winner_team"] == home_team
        winner = "home" if home_won else "away"
        home_pts, away_pts = (
            (hit["winner_pts"], hit["loser_pts"]) if home_won
            else (hit["loser_pts"], hit["winner_pts"])
        )
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
