"""
NFL Game Stats Crawler
Fetches NFL game statistics from Pro Football Reference
Extracts: date, teams (home/away), scores, rushing yards, passing yards
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
from datetime import datetime
import re
import argparse
import os
from urllib.robotparser import RobotFileParser

# Pro Football Reference base URL
PFR_BASE_URL = "https://www.pro-football-reference.com"

# User agent for requests (respectful crawler)
USER_AGENT = "Mozilla/5.0 (compatible; NFLStatsCrawler/1.0; +https://github.com/user/nfl-crawler)"

# Crawl delay in seconds (be respectful to the server)
CRAWL_DELAY = 2

# Maximum retries for 429 errors
MAX_RETRIES = 3

def check_robots_txt(url_path):
    """
    Check if a URL path is allowed by robots.txt.
    
    Args:
        url_path: Path to check (e.g., '/years/2020/week_1.htm')
    
    Returns:
        True if allowed, False otherwise
    """
    try:
        rp = RobotFileParser()
        rp.set_url(f"{PFR_BASE_URL}/robots.txt")
        rp.read()
        return rp.can_fetch(USER_AGENT, f"{PFR_BASE_URL}{url_path}")
    except Exception as e:
        print(f"  Warning: Could not check robots.txt: {e}")
        # If we can't check, be conservative and allow (but still be respectful)
        return True

def fetch_with_retry(url, timeout=15, max_retries=MAX_RETRIES, context=""):
    """
    Fetch a URL with retry logic for 429 (Too Many Requests) errors.
    
    Args:
        url: URL to fetch
        timeout: Request timeout in seconds
        max_retries: Maximum number of retries
        context: Context string for logging (e.g., "week page" or "boxscore")
    
    Returns:
        Response object or None if all retries failed
    """
    headers = {'User-Agent': USER_AGENT}
    
    for attempt in range(max_retries + 1):
        try:
            response = requests.get(url, timeout=timeout, headers=headers)
            
            if response.status_code == 429:
                # Extract Retry-After header
                retry_after = response.headers.get('Retry-After')
                
                print(f"  ERROR 429: Too Many Requests when fetching {context}")
                print(f"  Response Status: {response.status_code}")
                print(f"  Response Headers: {dict(response.headers)}")
                print(f"  Response Text (first 500 chars): {response.text[:500]}")
                
                if retry_after:
                    try:
                        wait_time = int(retry_after)
                        print(f"  Retry-After header: {wait_time} seconds")
                    except ValueError:
                        # Retry-After might be a date, try to parse it
                        print(f"  Retry-After header: {retry_after} (could not parse as integer)")
                        wait_time = CRAWL_DELAY * (attempt + 1)  # Fallback: exponential backoff
                else:
                    print(f"  No Retry-After header found, using exponential backoff")
                    wait_time = CRAWL_DELAY * (2 ** attempt)  # Exponential backoff: 2, 4, 8 seconds
                
                if attempt < max_retries:
                    print(f"  Waiting {wait_time} seconds before retry {attempt + 1}/{max_retries}...")
                    time.sleep(wait_time)
                    continue
                else:
                    print(f"  Max retries ({max_retries}) reached. Giving up.")
                    return None
            
            # For other status codes, raise an exception to be handled by caller
            response.raise_for_status()
            return response
            
        except requests.exceptions.RequestException as e:
            if attempt < max_retries and '429' in str(e):
                # Handle 429 in exception message
                print(f"  ERROR 429: Too Many Requests (in exception)")
                wait_time = CRAWL_DELAY * (2 ** attempt)
                print(f"  Waiting {wait_time} seconds before retry {attempt + 1}/{max_retries}...")
                time.sleep(wait_time)
                continue
            else:
                # Re-raise other exceptions
                raise
    
    return None

def get_week_url(year, week):
    """
    Get URL for a specific week in the NFL season.
    
    Args:
        year: Season year
        week: Week number (1-18 for regular season, or 'wild-card', 'divisional', 'conference', 'super-bowl' for playoffs)
    
    Returns:
        Week URL string
    """
    if isinstance(week, int):
        week_url = f"{PFR_BASE_URL}/years/{year}/week_{week}.htm"
    else:
        week_url = f"{PFR_BASE_URL}/years/{year}/{week}.htm"
    return week_url

def parse_game_summary(game_summary_div, year=2020):
    """
    Parse a single game summary div from Pro Football Reference.
    
    Args:
        game_summary_div: BeautifulSoup element with class "game_summary expanded nohover"
        year: Season year
    
    Returns:
        Dictionary with game data or None if invalid
    """
    try:
        # Find the teams table
        teams_table = game_summary_div.find('table', class_='teams')
        if not teams_table:
            return None
        
        # Extract date from <tr class="date">
        date_str = None
        date_row = teams_table.find('tr', class_='date')
        if date_row:
            date_text = date_row.get_text().strip()
            # Parse date like "Sep 28, 2020"
            try:
                date_obj = datetime.strptime(date_text, '%b %d, %Y')
                date_str = date_obj.strftime('%Y-%m-%d')
            except ValueError:
                # Try alternative format
                try:
                    date_obj = datetime.strptime(date_text, '%B %d, %Y')
                    date_str = date_obj.strftime('%Y-%m-%d')
                except ValueError:
                    pass
        
        # Extract winner and loser teams
        winner_row = teams_table.find('tr', class_='winner')
        loser_row = teams_table.find('tr', class_='loser')
        
        if not winner_row or not loser_row:
            return None
        
        # Get winner team name and score
        winner_team_link = winner_row.find('a', href=re.compile(r'/teams/'))
        winner_score_cell = winner_row.find('td', class_='right')
        
        if not winner_team_link or not winner_score_cell:
            return None
        
        winner_team = winner_team_link.get_text().strip()
        winner_score = int(winner_score_cell.get_text().strip())
        
        # Get loser team name and score
        loser_team_link = loser_row.find('a', href=re.compile(r'/teams/'))
        loser_score_cell = loser_row.find('td', class_='right')
        
        if not loser_team_link or not loser_score_cell:
            return None
        
        loser_team = loser_team_link.get_text().strip()
        loser_score = int(loser_score_cell.get_text().strip())
        
        # Find the boxscore link from <td class="right gamelink">
        gamelink_td = winner_row.find('td', class_='right gamelink')
        if not gamelink_td:
            # Try alternative: look for any gamelink td
            gamelink_td = teams_table.find('td', class_=re.compile(r'gamelink'))
        
        home_team = None
        away_team = None
        home_score = None
        away_score = None
        game_url = None
        
        # Team abbreviation to name mapping
        team_abbr_map = {
            'ari': 'Arizona Cardinals', 'atl': 'Atlanta Falcons', 'bal': 'Baltimore Ravens',
            'buf': 'Buffalo Bills', 'car': 'Carolina Panthers', 'chi': 'Chicago Bears',
            'cin': 'Cincinnati Bengals', 'cle': 'Cleveland Browns', 'dal': 'Dallas Cowboys',
            'den': 'Denver Broncos', 'det': 'Detroit Lions', 'gb': 'Green Bay Packers',
            'hou': 'Houston Texans', 'ind': 'Indianapolis Colts', 'jax': 'Jacksonville Jaguars',
            'kan': 'Kansas City Chiefs', 'kc': 'Kansas City Chiefs', 'lv': 'Las Vegas Raiders',
            'lac': 'Los Angeles Chargers', 'lar': 'Los Angeles Rams', 'mia': 'Miami Dolphins',
            'min': 'Minnesota Vikings', 'ne': 'New England Patriots', 'no': 'New Orleans Saints',
            'nyg': 'New York Giants', 'nyj': 'New York Jets', 'phi': 'Philadelphia Eagles',
            'pit': 'Pittsburgh Steelers', 'sf': 'San Francisco 49ers', 'sea': 'Seattle Seahawks',
            'tb': 'Tampa Bay Buccaneers', 'ten': 'Tennessee Titans', 'was': 'Washington Football Team',
            'rav': 'Baltimore Ravens', 'jag': 'Jacksonville Jaguars'
        }
        
        # Extract boxscore URL from gamelink td
        if gamelink_td:
            boxscore_link = gamelink_td.find('a', href=re.compile(r'/boxscores/'))
            if boxscore_link and boxscore_link.get('href'):
                # Construct full URL
                href = boxscore_link.get('href')
                if href.startswith('/'):
                    game_url = 'https://www.pro-football-reference.com' + href
                else:
                    game_url = 'https://www.pro-football-reference.com/' + href
                
                # Extract home team abbreviation from URL
                url_match = re.search(r'(\d{8})([a-z]{2,3})\.htm', href)
                if url_match:
                    home_team_abbr = url_match.group(2)
                    home_team_name = team_abbr_map.get(home_team_abbr)
                    
                    # Match home team with winner or loser
                    if home_team_name == winner_team:
                        home_team = winner_team
                        home_score = winner_score
                        away_team = loser_team
                        away_score = loser_score
                    elif home_team_name == loser_team:
                        home_team = loser_team
                        home_score = loser_score
                        away_team = winner_team
                        away_score = winner_score
                    else:
                        # Try partial matching
                        if home_team_name and any(word.lower() in winner_team.lower() for word in home_team_name.split() if len(word) > 3):
                            home_team = winner_team
                            home_score = winner_score
                            away_team = loser_team
                            away_score = loser_score
                        else:
                            home_team = loser_team
                            home_score = loser_score
                            away_team = winner_team
                            away_score = winner_score
        
        # Fallback if we couldn't determine home/away
        if not home_team or not away_team:
            # Default: assume winner is home (not always correct but common)
            home_team = winner_team
            home_score = winner_score
            away_team = loser_team
            away_score = loser_score
        
        # Get rushing and passing yards from boxscore page
        # Find div with id="div_team_stats" and extract Rush-Yds-TDs and Net Pass Yards
        home_rushing = None
        away_rushing = None
        home_passing = None
        away_passing = None
        
        if game_url:
            try:
                # Check robots.txt for boxscore page
                boxscore_path = game_url.replace(PFR_BASE_URL, '')
                if not check_robots_txt(boxscore_path):
                    print(f"    Warning: {boxscore_path} is disallowed by robots.txt, skipping stats...")
                else:
                    time.sleep(CRAWL_DELAY)  # Be respectful to the server
                    game_response = fetch_with_retry(game_url, timeout=10, context=f"boxscore ({home_team} vs {away_team})")
                    if game_response is None:
                        print(f"    Failed to fetch boxscore after retries, skipping stats...")
                    else:
                        game_soup = BeautifulSoup(game_response.content, 'html.parser')
                        
                        # Find div with id="div_team_stats"
                        team_stats_div = game_soup.find('div', {'id': 'div_team_stats'})
                        
                        if team_stats_div:
                            # Find the table inside this div
                            stats_table = team_stats_div.find('table')
                            
                            if stats_table:
                                rows = stats_table.find_all('tr')
                                for row in rows:
                                    header = row.find('th')
                                    if header:
                                        stat_name = header.get_text().strip().lower()
                                        cells = row.find_all('td')
                                        
                                        if len(cells) >= 2:
                                            try:
                                                # Look for "Rush-Yds-TDs" - extract the yards part
                                                if 'rush' in stat_name and ('yds' in stat_name or 'tds' in stat_name):
                                                    # The format is usually like "Rush-Yds-TDs" and values are like "25-120-1"
                                                    # We need to extract the middle number (yards)
                                                    away_value = cells[0].get_text().strip()
                                                    home_value = cells[1].get_text().strip()
                                                    
                                                    # Parse format like "25-120-1" to get yards (middle number)
                                                    away_parts = away_value.split('-')
                                                    home_parts = home_value.split('-')
                                                    
                                                    if len(away_parts) >= 2 and len(home_parts) >= 2:
                                                        away_rushing = int(away_parts[1].replace(',', ''))
                                                        home_rushing = int(home_parts[1].replace(',', ''))
                                                
                                                # Look for "Net Pass Yards" or "Pass Yds"
                                                elif 'net' in stat_name and 'pass' in stat_name and 'yds' in stat_name:
                                                    away_passing = int(cells[0].get_text().strip().replace(',', ''))
                                                    home_passing = int(cells[1].get_text().strip().replace(',', ''))
                                                elif 'pass' in stat_name and 'yds' in stat_name and 'net' not in stat_name:
                                                    # Sometimes it's just "Pass Yds" without "Net"
                                                    away_passing = int(cells[0].get_text().strip().replace(',', ''))
                                                    home_passing = int(cells[1].get_text().strip().replace(',', ''))
                                            except (ValueError, IndexError, AttributeError) as e:
                                                pass
                
            except Exception as e:
                print(f"    Warning: Could not fetch stats from {game_url}: {e}")
        
        # Validate we have minimum required data
        if not date_str or not home_team or not away_team or home_score is None or away_score is None:
            return None
        
        return {
            'Date': date_str,
            'Home Team': home_team,
            'Away Team': away_team,
            'Home Score': home_score,
            'Away Score': away_score,
            'Home Rushing Yards': home_rushing,
            'Away Rushing Yards': away_rushing,
            'Home Passing Yards': home_passing,
            'Away Passing Yards': away_passing
        }
    
    except Exception as e:
        print(f"  Error parsing game summary: {e}")
        return None

def fetch_week_games(week_url, year=2020):
    """
    Fetch all games from a specific week.
    
    Args:
        week_url: URL of the week page
        year: Season year
    
    Returns:
        List of game dictionaries
    """
    games = []
    
    try:
        # Check robots.txt compliance
        url_path = week_url.replace(PFR_BASE_URL, '')
        if not check_robots_txt(url_path):
            print(f"  Warning: {url_path} is disallowed by robots.txt, skipping...")
            return games
        
        print(f"Fetching: {week_url}")
        response = fetch_with_retry(week_url, timeout=15, context="week page")
        if response is None:
            print(f"  Failed to fetch week page after retries")
            return games
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Find all game summary divs with class "game_summary expanded nohover"
        # Handle both string and list class attributes
        def has_game_summary_class(tag):
            if tag.name != 'div':
                return False
            classes = tag.get('class', [])
            if isinstance(classes, str):
                classes = classes.split()
            return 'game_summary' in classes and 'expanded' in classes and 'nohover' in classes
        
        game_summaries = soup.find_all(has_game_summary_class)
        
        if not game_summaries:
            # Try finding by class string match
            game_summaries = soup.find_all('div', class_='game_summary expanded nohover')
        
        if not game_summaries:
            # Try finding any div with game_summary class
            game_summaries = soup.find_all('div', class_=re.compile(r'game_summary'))
        
        if not game_summaries:
            print(f"  No game summaries found for {week_url}")
            return games
        
        print(f"  Found {len(game_summaries)} game summaries")
        
        for summary_div in game_summaries:
            game_data = parse_game_summary(summary_div, year)
            if game_data:
                games.append(game_data)
        
        print(f"  Successfully parsed {len(games)} games")
        
    except requests.exceptions.RequestException as e:
        print(f"  Error fetching {week_url}: {e}")
    except Exception as e:
        print(f"  Error processing {week_url}: {e}")
        import traceback
        traceback.print_exc()
    
    return games

def main():
    """
    Main function to fetch NFL game stats and save to CSV.
    """
    parser = argparse.ArgumentParser(
        description='NFL Game Stats Crawler - Fetches game statistics from Pro Football Reference',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python nfl_crawler.py --year 2020 --week 1
  python nfl_crawler.py --year 2020 --week 10
  python nfl_crawler.py --year 2020 --week wild-card
  python nfl_crawler.py --year 2020 --week super-bowl
        """
    )
    parser.add_argument(
        '--year',
        type=int,
        required=True,
        help='Year of the NFL season (e.g., 2020)'
    )
    parser.add_argument(
        '--week',
        type=str,
        required=True,
        help='Week number (1-18) or playoff round (wild-card, divisional, conference, super-bowl)'
    )
    
    args = parser.parse_args()
    
    year = args.year
    week = args.week
    
    # Validate week input
    if week.isdigit():
        week_num = int(week)
        if week_num < 1 or week_num > 18:
            print(f"Error: Week must be between 1 and 18, got {week_num}")
            return
    elif week not in ['wild-card', 'divisional', 'conference', 'super-bowl']:
        print(f"Error: Invalid week '{week}'. Must be 1-18 or one of: wild-card, divisional, conference, super-bowl")
        return
    
    print("=" * 70)
    print(f"NFL Game Stats Crawler - {year} Season, Week {week}")
    print("=" * 70)
    print()
    print(f"User-Agent: {USER_AGENT}")
    print(f"Crawl Delay: {CRAWL_DELAY} seconds")
    print()
    
    # Generate output filename with year and week
    week_str = str(week).replace('-', '_')
    output_file = f'dev_data/nfl_{year}_week_{week_str}_game_stats.csv'
    print(f"Output file: {output_file}")
    print()
    
    # Get week URL
    week_url = get_week_url(year, week)
    
    # Fetch games from the specified week
    print(f"Fetching games from Week {week}...")
    games = fetch_week_games(week_url, year)
    
    if not games:
        print("Error: No game data was retrieved.")
        return
    
    # Create DataFrame
    df = pd.DataFrame(games)
    
    # Sort by date
    df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
    df = df.sort_values('Date')
    df['Date'] = df['Date'].dt.strftime('%Y-%m-%d')
    
    # Reorder columns
    column_order = ['Date', 'Home Team', 'Away Team', 'Home Score', 'Away Score',
                   'Home Rushing Yards', 'Away Rushing Yards', 
                   'Home Passing Yards', 'Away Passing Yards']
    df = df[column_order]
    
    # Create output directory if it doesn't exist
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    # Save to CSV
    df.to_csv(output_file, index=False)
    
    print()
    print("=" * 70)
    print(f"Successfully saved {len(df)} games to {output_file}")
    print("=" * 70)
    print()
    print("Sample data:")
    print(df.head(10).to_string(index=False))
    print()
    print(f"Data saved to: {output_file}")
    print()
    print(f"Total games: {len(df)}")
    print(f"Games with complete stats: {df[['Home Rushing Yards', 'Home Passing Yards']].notna().all(axis=1).sum()}")

if __name__ == "__main__":
    main()

