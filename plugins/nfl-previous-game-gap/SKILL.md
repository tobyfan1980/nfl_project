---
name: nfl-previous-game-gap
description: Find the calendar-day gap between a team's most recent completed game and a supplied next-game date from an NFL season games CSV. Use for files such as `dev_data/games/2025_games.csv`, not for travel or player-rest analysis.
---

# NFL Previous Game Gap

Use `scripts/previous_game_gap.py` to calculate the interval deterministically from a season games file.

```bash
python3 <skill-dir>/scripts/previous_game_gap.py \
  --games-file /path/to/nfl_project/dev_data/games/2025_games.csv \
  --team "Kansas City Chiefs" \
  --next-game-date 2025-10-12
```

## Inputs

- `--team`: Full team name exactly as it appears in the CSV.
- `--next-game-date`: Date of the upcoming game in `YYYY-MM-DD` format.
- `--games-file`: Season games CSV, such as `dev_data/games/2025_games.csv`.

## Behavior

- Select the latest completed game strictly before `--next-game-date` in which the team appears as either winner or loser.
- Ignore incomplete or separator rows.
- Calculate `next_game_date - previous_game_date` as calendar days.
- Report the previous game, its opponent and score, and the day count. If no earlier completed game is available, report that explicitly.

## Generate Season Files

Use `scripts/generate_season_game_intervals.py` to create one
`yyyy_game_intervals.csv` file for every available `yyyy_games.csv` file. It
creates one row for each team-game in completed regular-season Weeks 2 through
18, with the current game date, prior game date, opponent, and calendar-day
interval.

```bash
python3 <skill-dir>/scripts/generate_season_game_intervals.py \
  --input-dir /path/to/nfl_project/dev_data/games \
  --output-dir /path/to/nfl_project/dev_data/metrics
```

Use `--years 2023 2024` to limit processing. Existing outputs are protected
unless `--overwrite` is passed.
