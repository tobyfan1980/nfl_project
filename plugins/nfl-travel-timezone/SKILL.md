---
name: nfl-travel-timezone
description: Calculate a team's travel miles and timezone changes from its latest completed NFL game to a specified home or away next-game city. Use for the repository's `*_games.csv` files, not for road-mile or flight-booking estimates.
---

# NFL Travel and Timezone

Use `scripts/calculate_travel.py` to apply the team's prior-game location and the requested next-game venue rules.

```bash
python3 <skill-dir>/scripts/calculate_travel.py \
  --games-file /path/to/nfl_project/dev_data/games/2025_games.csv \
  --team "Kansas City Chiefs" \
  --venue away \
  --next-game-city "Denver, CO"
```

## Required Inputs

- `--team`: Full team name as it appears in the game file.
- `--venue`: `home` or `away` for the next game.
- `--next-game-city`: City of the next game. For a home game, it must resolve to the team's catalogued home-stadium city.
- `--games-file`: A repository-style season game CSV.

## Behavior

- Use the latest completed game in which the team appears. The game marker identifies whether that prior game was home or away.
- Use great-circle miles between stadium-city coordinates, not driving miles. The calculation is deterministic and needs no network or API key.
- Use IANA time zones and the prior-game date for daylight-saving-aware offsets. Pass optional `--next-game-date` when the next game crosses a daylight-saving transition.
- For a next home game, prior home means zero travel; prior away means travel directly to the team home city.
- For a next away game, prior home means travel from home to the next city. Prior away uses the home detour only when its miles are strictly less than twice the direct route; otherwise it uses the direct route.
- `timezone_transition_hours` is the sum of absolute timezone changes on the selected legs. `net_timezone_change_hours` is the signed difference from the first to last city.
- Neutral previous games use the catalog's date-and-matchup override because this CSV format stores a nominal-home ZIP. Add an override for a new neutral game, or use `--previous-game-city` when no override exists.

The maintained location data is in [references/nfl_stadium_locations.json](references/nfl_stadium_locations.json). Add a location there when a requested city is not yet supported.

## Generate Season Files

Use `scripts/generate_season_travel.py` to create one `yyyy_travel-timezone.csv` file for every available `yyyy_games.csv` file. It writes two rows per valid regular-season game from Weeks 2 through 18, one for the nominal home team and one for the away team. Each row uses only games before that game's date.

```bash
python3 <skill-dir>/scripts/generate_season_travel.py \
  --input-dir /path/to/nfl_project/dev_data/games \
  --output-dir /path/to/nfl_project/dev_data/metrics
```

Use `--years 2023 2024` to limit processing. Existing outputs are protected unless `--overwrite` is passed.
