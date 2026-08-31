---
name: nfl-opponent-strength
description: Calculate the average previous-five-game win rate of a team's five most recent opponents from an NFL season games CSV. Use for opponent-strength features from files such as `dev_data/games/2025_games.csv`, not for future projections or player ratings.
---

# NFL Opponent Strength

Use `scripts/opponent_strength.py` to calculate the feature without data leakage.

```bash
python3 <skill-dir>/scripts/opponent_strength.py \
  --games-file /path/to/nfl_project/dev_data/games/2025_games.csv \
  --team "Kansas City Chiefs" \
  --current-date 2025-10-12
```

Use `scripts/generate_season_opponent_strength.py` to generate model-ready CSVs
for regular-season Weeks 6 through 18. Omit `--years` to discover every
`yyyy_games.csv` file in dev_data/games/.

```bash
python3 <skill-dir>/scripts/generate_season_opponent_strength.py \
  --input-dir /path/to/nfl_project/dev_data \
  --output-dir /path/to/nfl_project/dev_data
```

## Inputs

- `--team`: Full team name exactly as it appears in the CSV.
- `--current-date`: Cutoff date in `YYYY-MM-DD` format. Only earlier completed games count.
- `--games-file`: Season games CSV, such as `dev_data/games/2025_games.csv`.

## Behavior

- Select the team's five most recent completed games before `--current-date`; every game supplies one opponent, even if an opponent appears more than once.
- For each selected opponent, take that opponent's five most recent completed games before the same cutoff date.
- Compute the opponent win rate as `wins / 5`, as specified. Ties count as non-wins and an opponent with fewer than five available games still uses `5` as the denominator.
- Average the five opponent win rates and report `opponent_strength_average_win_rate`.
- The single-team command reports selected opponents and component rates for auditing.
- Season CSVs contain only `week`, `date`, `team`, and `opponent_strength_average_win_rate` so they can be joined directly to model data.
