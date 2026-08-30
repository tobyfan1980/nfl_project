---
name: nfl-game-data-collector
description: Collect completed NFL season game results into this nfl_project repository's 17-column *_games.csv format. Use when adding, refreshing, or validating a season game file; not for play-level or player-stat datasets.
---

# NFL Game Data Collector

Use `scripts/collect_games.py` for deterministic collection. It combines nflverse schedules and play-by-play metadata with ESPN completed box scores, then validates the result before an atomic write.

Run from any directory:

```bash
python3 <skill-dir>/scripts/collect_games.py \
  --year 2025 \
  --repo /path/to/nfl_project
```

The default output is `<repo>/dev_data/<year>_games.csv`. If it already exists, inspect it and use `--overwrite` only when replacing it is part of the user's request. Use `--cache-dir` to retain source downloads across runs and `--workers` to adjust ESPN concurrency; keep the default unless there is a demonstrated need.

## Required Invariants

- Preserve the exact 17-column header, including the duplicate `Date` header and blank venue-marker header.
- Include only completed games. Keep regular-season games first, one blank separator row, then postseason games.
- Use ESPN box-score total yards and turnovers because play-by-play aggregation can differ after official stat corrections.
- Keep unavailable weather fields blank; never substitute current weather for historical weather.
- Preserve the repository's ZIP convention: use the nominal home team's stadium ZIP, including neutral and international games.
- Do not publish partial results. A missing box score, team mismatch, malformed row, or missing core field must fail the run.

After collection, report the output path, game counts, postseason breakdown, and weather completeness. Cite the sources printed by the script when provenance is useful.
