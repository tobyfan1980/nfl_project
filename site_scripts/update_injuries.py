"""Refresh only the injury report for the week currently on the site.

    python site_scripts/update_injuries.py [--data-dir site/data]

Reads ``current_week`` from season.json and rewrites injuries.json (nfl.com,
falling back to the nflverse report). Picks, results and accuracy are not
touched. Run it on the nights the league posts new reports (Wed/Fri/Sat),
then ``git add site/data/injuries.json && git commit && git push``.
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fetch_injuries import fetch_injury_report  # noqa: E402
from update_week import DEFAULT_DATA_DIR, _read_json, _write_json  # noqa: E402


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data-dir", default=str(DEFAULT_DATA_DIR))
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    data_dir = Path(args.data_dir)
    season_json = _read_json(data_dir / "season.json", {})
    season, week = season_json.get("season"), season_json.get("current_week")
    if not season or not week:
        print(f"No season/current_week in {data_dir / 'season.json'}; run update_week.py first.")
        return 1

    injuries = fetch_injury_report(season, week)
    status = _write_json(data_dir / "injuries.json", injuries)
    teams = injuries.get("teams", {})
    players = sum(len(v) for v in teams.values())
    print(f"PocketPicks {season} week {week} injuries: "
          + (f"{len(teams)} teams, {players} players" if injuries["available"]
             else f"unavailable ({injuries.get('reason')})"))
    print(f"  {status:9s} {data_dir / 'injuries.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
