# NFL Game Stats Crawler

This project fetches NFL game statistics from Pro Football Reference for the 2020 season.

## Data Source

The crawler uses **Pro Football Reference** (https://www.pro-football-reference.com), a comprehensive and reliable source for NFL statistics. This site provides detailed game-by-game data including scores, rushing yards, and passing yards.

## Features

- Fetches game data for all weeks of the 2020 NFL season (regular season + playoffs)
- Extracts the following data for each game:
  - Date
  - Home Team
  - Away Team
  - Home Score
  - Away Score
  - Home Rushing Yards
  - Away Rushing Yards
  - Home Passing Yards
  - Away Passing Yards
- Saves data to CSV format

## Installation

1. Install required Python packages:

```bash
pip install -r requirements.txt
```

## Usage

Run the crawler script with year and week parameters:

```bash
# Fetch a specific week from a season
python nfl_crawler.py --year 2020 --week 1

# Fetch a playoff round
python nfl_crawler.py --year 2020 --week wild-card
python nfl_crawler.py --year 2020 --week super-bowl

# Examples
python nfl_crawler.py --year 2020 --week 10
python nfl_crawler.py --year 2021 --week 5
```

### Parameters

- `--year` (required): Year of the NFL season (e.g., 2020, 2021)
- `--week` (required): Week number (1-18) or playoff round:
  - Regular season: `1` through `18`
  - Playoffs: `wild-card`, `divisional`, `conference`, `super-bowl`

The script will:
1. Check robots.txt compliance before crawling
2. Fetch game data from the specified week
3. Visit each game's boxscore page to get detailed stats (rushing/passing yards)
4. Process and format the data
5. Save results to `nfl_{year}_week_{week}_game_stats.csv`

**Note:** The script includes delays (2 seconds) between requests to be respectful to the server and follows robots.txt guidelines. Each week may take 1-2 minutes depending on the number of games and your internet connection.

## Output

The CSV file contains the following columns:
- **Date**: Game date in YYYY-MM-DD format
- **Home Team**: Home team name
- **Away Team**: Away team name
- **Home Score**: Final score for home team
- **Away Score**: Final score for away team
- **Home Rushing Yards**: Total rushing yards for home team
- **Away Rushing Yards**: Total rushing yards for away team
- **Home Passing Yards**: Total passing yards for home team
- **Away Passing Yards**: Total passing yards for away team

## Robots.txt Compliance

The crawler respects Pro Football Reference's robots.txt guidelines:
- Checks robots.txt before accessing any URL
- Uses a proper User-Agent header
- Implements a 2-second crawl delay between requests
- Skips URLs that are disallowed by robots.txt

## Notes

- The script includes delays (2 seconds) between requests to be respectful to Pro Football Reference's servers
- Some games may have missing rushing/passing yard data if the boxscore page structure differs
- The script handles both regular season and playoff games
- Games are sorted by date in the output CSV
- The crawler checks robots.txt compliance before each request

## Troubleshooting

If you encounter issues:
- Check your internet connection
- Verify that Pro Football Reference is accessible
- Some games may fail to parse if the page structure has changed - the script will continue with other games
- If many games are missing stats, the site structure may have changed and the parser may need updates

