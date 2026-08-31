# NFL Project

A comprehensive NFL data analysis project that includes web scraping tools for game statistics and rating calculation systems.

## Project Overview

This project provides tools for:
- Scraping NFL game statistics from Pro Football Reference
- Scraping weather data from NOAA
- Calculating offensive and defensive ratings for NFL teams per game

## Project Structure

```
nfl_project/
├── tools/
│   ├── nfl_crawler.py      # NFL game stats crawler
│   └── weather_crawler.py  # Weather data crawler
├── calculate_rating_per_game.py  # Calculate team ratings from game data
├── model.py                # NFL rating model definitions
├── requirements.txt        # Python dependencies
└── README.md              # This file
```

## Installation

1. Install required Python packages:

```bash
pip install -r requirements.txt
```

## Features

### 1. NFL Game Stats Crawler

Scrapes NFL game statistics from Pro Football Reference for any season and week.

**Location**: `tools/nfl_crawler.py`

**Usage**:
```bash
# Fetch a specific week from a season
python tools/nfl_crawler.py --year 2020 --week 1

# Fetch a playoff round
python tools/nfl_crawler.py --year 2020 --week wild-card
python tools/nfl_crawler.py --year 2020 --week super-bowl
```

**Parameters**:
- `--year` (required): Year of the NFL season (e.g., 2020, 2021)
- `--week` (required): Week number (1-18) or playoff round (`wild-card`, `divisional`, `conference`, `super-bowl`)

**Output**: Creates `dev_data/games/nfl_{year}_week_{week}_game_stats.csv` with:
- Date
- Home Team
- Away Team
- Home/Away Scores
- Home/Away Rushing Yards
- Home/Away Passing Yards

**Features**:
- Robots.txt compliant
- Handles 429 rate limiting errors with retry logic
- Respects crawl delays

### 2. Weather Data Enrichment

Adds historical temperature and conditions to a season game-results file using
the stadium ZIP code.

**Location**: `tools/weather_crawler.py`

**Usage**:
```bash
# Enrich the 2024 game results in place
python tools/weather_crawler.py --games-file dev_data/games/2024_games.csv

# Write enriched results to a separate game-results file
python tools/weather_crawler.py \
  --games-file dev_data/games/2024_games.csv \
  --output dev_data/games/2024_games_weather.csv
```

**Output**: Updates the supplied game-results CSV, or writes the requested
output file, with `temperature` and `condition` columns. Configure the
selected weather API key in `.env`.

### 3. NFL Rating Calculator

Calculates offensive and defensive ratings for each team per game based on game statistics.

**Location**: `calculate_rating_per_game.py`

**Usage**:
```bash
python calculate_rating_per_game.py --year 2024
```

**Input**: `dev_data/games/2024_games.csv` (or similar game data file)

**Output**: `dev_data/metrics/2024_game_ratings_v2.csv` with columns:
- `team`: Team name
- `score`: Points scored
- `win_lose`: 'W' or 'L'
- `home_away`: 'Home' or 'Away'
- `offensive_rating`: Calculated offensive rating
- `defensive_rating`: Calculated defensive rating

**Rating Formulas**:

- **Offensive Rating**: 
  ```
  sqrt(yards/5 + 40) * 2 + sqrt(points * 5 * sqrt(2) * 0.6) * 5
  ```

- **Defensive Rating**: 
  ```
  yards_opponent/72 - (25 * turnovers_opponent + 72)/72 + 1.3 * points_opponent/11
  ```

## Model Definitions

The `model.py` file contains the `NFLModel1` class with methods for calculating:
- `offensive_rating(yards, points)`: Calculates offensive performance rating
- `defensive_rating(yards_op, points_op, to_op)`: Calculates defensive performance rating

## Data Files

CSV data is organized by role under `dev_data/`:
- `dev_data/games/2022_games.csv`: Game data for the 2022 season
- `dev_data/metrics/2022_game_ratings.csv`: Calculated ratings for the 2022 season
- `dev_data/games/2023_games.csv`: Game data for the 2023 season
- `dev_data/games/2024_games.csv`: Game data for the 2024 season
- `dev_data/metrics/`: Ratings and derived win-rate, travel, interval, and
  opponent-strength features
- `dev_data/reference/`: Shared stadium and team mappings
- `backlog/`: Archive of previous data files

## Requirements

- Python 3.6+
- requests
- pandas
- beautifulsoup4
- lxml

## Notes

- All crawlers respect robots.txt guidelines
- Crawlers include appropriate delays to be respectful to servers
- Rate limiting (429 errors) are handled with automatic retry logic
- CSV files outside `dev_data/` are ignored by git; game, metric, and
  reference CSVs under `dev_data/` are versioned.

## License

This project is for educational and research purposes.
