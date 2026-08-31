# Repository Guidelines

## Project Structure & Module Organization
This repository is a small Python workflow for collecting NFL data and deriving per-game ratings. Core scripts live at the repo root: `calculate_rating_per_game.py` builds rating outputs, `model.py` contains rating formulas, and `add_zipcodes.py` enriches game files. Crawlers and one-off maintenance utilities live in `tools/`, including `tools/nfl_crawler.py` and `tools/weather_crawler.py`. Raw season results live in `dev_data/games/`, derived features and ratings in `dev_data/metrics/`, and shared lookup data in `dev_data/reference/`. Progress notes and working context go in `project_log/` and `backlog/`.

## Build, Test, and Development Commands
Install dependencies with `pip install -r requirements.txt`.

Common commands:
- `python calculate_rating_per_game.py --year 2024` generates `dev_data/metrics/2024_game_ratings_v2.csv`.
- `python tools/nfl_crawler.py --year 2024 --week 1` fetches one week of game data.
- `python tools/weather_crawler.py` enriches games with weather data if API keys are configured.
- `python -m py_compile model.py calculate_rating_per_game.py tools/*.py` performs a quick syntax check before committing.

Run commands from the repository root so relative paths like `dev_data/games/2024_games.csv` resolve correctly.

## Coding Style & Naming Conventions
Use Python with 4-space indentation, standard library first in imports, and small single-purpose functions. Keep filenames and functions in `snake_case`; classes use `PascalCase` like `NFLModel1`. Preserve the existing CLI style based on `argparse`, explicit prints, and CSV-oriented pipelines. Prefer clear variable names tied to football data (`winner_score`, `loser_turnovers`) over abbreviations.

## Testing Guidelines
There is no dedicated automated test suite yet. For now, validate changes with targeted script runs against `dev_data/` samples and a syntax pass with `python -m py_compile`. When adding logic, verify both the generated CSV schema and a few representative rows. If you add formal tests later, place them in a new `tests/` directory and name files `test_<feature>.py`.

## Commit & Pull Request Guidelines
Recent history favors short, imperative commit messages such as `add weather and zipcode` and `add turnover to offensive rating`. Keep commits focused on one change. Pull requests should include a brief summary, affected scripts or datasets, sample command(s) used for validation, and before/after output notes when CSV columns or formulas change.

## Security & Configuration Tips
Keep API keys in `.env`; do not hardcode secrets in scripts or commit the file contents. Treat `dev_data/` as working data: review large CSV diffs carefully before including them in a PR.
