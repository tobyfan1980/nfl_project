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

**Output**: Creates `dev_data/nfl_{year}_week_{week}_game_stats.csv` with:
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

### 2. Weather Data Crawler

Fetches historical weather data from NOAA NCEI API.

**Location**: `tools/weather_crawler.py`

**Usage**:
```bash
# Default (Seattle)
python tools/weather_crawler.py

# Specify a city
python tools/weather_crawler.py --city seattle
python tools/weather_crawler.py --city "new york"
```

**Output**: Creates `dev_data/{city}_weather_2024.csv` with:
- City
- Date
- High Temperature (°F)
- Condition

### 3. NFL Rating Calculator

Calculates offensive and defensive ratings for each team per game based on game statistics.

**Location**: `calculate_rating_per_game.py`

**Usage**:
```bash
python calculate_rating_per_game.py
```

**Input**: `dev_data/2022_games.csv` (or similar game data file)

**Output**: `dev_data/2022_game_ratings.csv` with columns:
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

All CSV data files are stored in the `dev_data/` folder:
- `dev_data/2022_games.csv`: Game data for 2022 season
- `dev_data/2022_game_ratings.csv`: Calculated ratings for 2022 season
- `dev_data/2023_games.csv`: Game data for 2023 season
- `dev_data/2024_games.csv`: Game data for 2024 season
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
- CSV files are ignored by git (see `.gitignore`)

## License

This project is for educational and research purposes.
