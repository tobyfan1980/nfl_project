---
name: nfl-previous-five-win-rate
description: Compute a team's win rate across its five most recent completed games before a target date from an NFL season games CSV. Use for files like `dev_data/2025_games.csv`, not for player stats or future projections.
---

# NFL Previous Five Win Rate

Use `scripts/previous_five_win_rate.py` for deterministic calculation from this repository's season game files.

Run:

```bash
python3 <skill-dir>/scripts/previous_five_win_rate.py \
  --games-file /path/to/nfl_project/dev_data/2025_games.csv \
  --date 2025-10-12 \
  --team "Kansas City Chiefs"
```

## Inputs

- `--date`: target date in `YYYY-MM-DD` format. Only games strictly before this date count.
- `--team`: full team name as it appears in the CSV, such as `Philadelphia Eagles`.
- `--games-file`: season game CSV, such as `dev_data/2025_games.csv`.

## Behavior

- Treat both `Winner/tie` and `Loser/tie` as appearances for the team.
- Use the score columns to classify each prior game as win, loss, or tie.
- Count ties as `0.5` wins when computing the win rate.
- Ignore separator rows or incomplete rows.
- If fewer than five prior games exist, use all available completed prior games and report that count explicitly.

Report the selected games, the record over that span, and the computed win rate.

## Generate Season Files

Use `scripts/generate_season_win_rates.py` to create one `yyyy_win_rate.csv` file for every available `yyyy_games.csv` file. It creates a row for each team-game from regular-season Weeks 6 through 18; the rate uses only games before that row's date.

```bash
python3 <skill-dir>/scripts/generate_season_win_rates.py \
  --input-dir /path/to/nfl_project/dev_data \
  --output-dir /path/to/nfl_project/dev_data
```

Use `--years 2023 2024` to limit processing. Existing outputs are protected unless `--overwrite` is passed.
