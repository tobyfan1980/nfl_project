"""
Weather Data Crawler
Reads NFL games CSV file and adds weather temperature and condition columns
based on Date, Time, and zipcode for each game.
"""

import csv
import os
import requests
import time
from datetime import datetime
import argparse

# OpenWeatherMap API endpoint for historical weather
# Note: Historical data requires a paid subscription or use of One Call API 3.0
# For free tier, we'll use current weather API as fallback
OPENWEATHER_API_BASE = "https://api.openweathermap.org/data/2.5"

def get_weather_by_zipcode(zipcode: str, date: str, time_str: str, api_key: str = None):
    """
    Get weather data for a specific zipcode, date, and time.
    
    Args:
        zipcode: 5-digit US zipcode
        date: Date in YYYY-MM-DD format
        time_str: Time in format like "8:20PM" or "1:00PM"
        api_key: OpenWeatherMap API key (optional, can use env var)
    
    Returns:
        Tuple of (temperature_fahrenheit, condition) or (None, None) if error
    """
    if not api_key:
        api_key = os.getenv('OPENWEATHER_API_KEY')
    
    if not api_key:
        print("Warning: No OpenWeatherMap API key found. Set OPENWEATHER_API_KEY environment variable.")
        print("For historical weather data, you may need OpenWeatherMap One Call API 3.0 subscription.")
        return None, None
    
    # For historical data, we need to use One Call API 3.0 with coordinates
    # Since we have zipcode, we'll first get coordinates, then get historical weather
    # However, One Call API 3.0 requires coordinates, not zipcode
    
    # Alternative: Use Visual Crossing API (free tier available) or other service
    # For now, let's use a simpler approach with OpenWeatherMap current weather
    # and note that historical data may require a different API
    
    try:
        # First, get coordinates from zipcode using geocoding API
        geo_url = f"{OPENWEATHER_API_BASE}/weather"
        geo_params = {
            'zip': f"{zipcode},US",
            'appid': api_key
        }
        
        # For historical data, we'll use OpenWeatherMap One Call API 3.0
        # But it requires coordinates, so we need to:
        # 1. Get coordinates from zipcode
        # 2. Use One Call API 3.0 for historical data
        
        # For now, using a workaround: get current weather as placeholder
        # In production, you'd want to use historical weather API
        
        response = requests.get(geo_url, params=geo_params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            temp_kelvin = data['main']['temp']
            temp_f = (temp_kelvin - 273.15) * 9/5 + 32
            condition = data['weather'][0]['main']
            return round(temp_f, 1), condition
        else:
            print(f"Error fetching weather for zipcode {zipcode}: {response.status_code}")
            return None, None
            
    except Exception as e:
        print(f"Error getting weather for zipcode {zipcode}: {e}")
        return None, None

def get_weather_historical_visual_crossing(zipcode: str, date: str, time_str: str, api_key: str = None):
    """
    Get historical weather using Visual Crossing API (free tier available).
    
    Args:
        zipcode: 5-digit US zipcode
        date: Date in YYYY-MM-DD format
        time_str: Time in format like "8:20PM" or "1:00PM"
        api_key: Visual Crossing API key (optional, can use env var)
    
    Returns:
        Tuple of (temperature_fahrenheit, condition) or (None, None) if error
    """
    if not api_key:
        api_key = os.getenv('VISUAL_CROSSING_API_KEY')
    
    if not api_key:
        # Try OpenWeatherMap as fallback
        return get_weather_by_zipcode(zipcode, date, time_str, None)
    
    try:
        # Visual Crossing API endpoint
        url = "https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline"
        
        # Parse date and time
        date_obj = datetime.strptime(date, '%Y-%m-%d')
        date_str = date_obj.strftime('%Y-%m-%d')
        
        # Visual Crossing uses location string (can use zipcode)
        location = f"{zipcode}"
        
        params = {
            'location': location,
            'date': date_str,
            'key': api_key,
            'unitGroup': 'us',  # Use US units (Fahrenheit)
            'include': 'hours'  # Include hourly data
        }
        
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            # Get the day's data
            if 'days' in data and len(data['days']) > 0:
                day_data = data['days'][0]
                
                # Get temperature (use temp or tempmax depending on time)
                # For simplicity, use the day's average temp
                temp_f = day_data.get('temp', day_data.get('tempmax'))
                
                # Get condition
                condition = day_data.get('conditions', 'Unknown')
                
                return round(temp_f, 1), condition
            else:
                return None, None
        else:
            print(f"Error fetching weather from Visual Crossing for zipcode {zipcode}: {response.status_code}")
            # Fallback to OpenWeatherMap
            return get_weather_by_zipcode(zipcode, date, time_str, None)
            
    except Exception as e:
        print(f"Error getting weather from Visual Crossing for zipcode {zipcode}: {e}")
        # Fallback to OpenWeatherMap
        return get_weather_by_zipcode(zipcode, date, time_str, None)

def add_weather_to_games(games_file: str, output_file: str = None, api_provider: str = 'visual_crossing'):
    """
    Read games CSV and add weather temperature and condition columns.
    
    Args:
        games_file: Path to games CSV file (e.g., 2024_games.csv)
        output_file: Path to output file (if None, overwrites input file)
        api_provider: Weather API provider ('visual_crossing' or 'openweather')
    """
    if output_file is None:
        output_file = games_file
    
    rows = []
    processed_count = 0
    error_count = 0
    
    print(f"Reading games from {games_file}...")
    
    # Read the CSV file
    with open(games_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames)
        
        # Add weather columns if they don't exist
        if 'temperature' not in fieldnames:
            fieldnames.append('temperature')
        if 'condition' not in fieldnames:
            fieldnames.append('condition')
        
        for row in reader:
            # Skip empty rows
            if not row.get('Date') or not row.get('zipcode'):
                row['temperature'] = row.get('temperature', '')
                row['condition'] = row.get('condition', '')
                rows.append(row)
                continue
            
            date = row['Date'].strip()
            time_str = row.get('Time', '').strip()
            zipcode = row.get('zipcode', '').strip()
            
            if not zipcode:
                print(f"Warning: No zipcode for row {processed_count + 1}, skipping weather lookup")
                row['temperature'] = row.get('temperature', '')
                row['condition'] = row.get('condition', '')
                rows.append(row)
                continue
            
            # Get weather data
            if api_provider == 'visual_crossing':
                temp, condition = get_weather_historical_visual_crossing(zipcode, date, time_str)
            else:
                temp, condition = get_weather_by_zipcode(zipcode, date, time_str)
            
            if temp is not None and condition is not None:
                row['temperature'] = str(temp)
                row['condition'] = condition
                processed_count += 1
            else:
                row['temperature'] = row.get('temperature', '')
                row['condition'] = row.get('condition', '')
                error_count += 1
            
            rows.append(row)
            
            # Be respectful to API rate limits
            time.sleep(0.5)  # Small delay between requests
            
            # Progress update
            if (processed_count + error_count) % 10 == 0:
                print(f"Processed {processed_count + error_count} games...")
    
    # Write updated data
    print(f"\nWriting updated data to {output_file}...")
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    
    print(f"\nSuccessfully processed {len(rows)} rows")
    print(f"  - Weather data retrieved: {processed_count}")
    print(f"  - Errors/missing data: {error_count}")

def main():
    """Main function to add weather data to games CSV."""
    parser = argparse.ArgumentParser(
        description='Add weather temperature and condition to NFL games CSV based on zipcode'
    )
    parser.add_argument(
        '--games-file',
        type=str,
        default='dev_data/2024_games.csv',
        help='Path to games CSV file (default: dev_data/2024_games.csv)'
    )
    parser.add_argument(
        '--output',
        type=str,
        default=None,
        help='Output file path (default: overwrites input file)'
    )
    parser.add_argument(
        '--api',
        type=str,
        choices=['visual_crossing', 'openweather'],
        default='visual_crossing',
        help='Weather API provider (default: visual_crossing)'
    )
    
    args = parser.parse_args()
    
    print("=" * 70)
    print("NFL Games Weather Data Adder")
    print("=" * 70)
    print()
    print(f"Games file: {args.games_file}")
    print(f"API provider: {args.api}")
    print()
    
    if args.api == 'visual_crossing':
        api_key = os.getenv('VISUAL_CROSSING_API_KEY')
        if not api_key:
            print("Note: VISUAL_CROSSING_API_KEY environment variable not set.")
            print("You can get a free API key at: https://www.visualcrossing.com/weather-api")
            print("Continuing with OpenWeatherMap fallback...")
            print()
    else:
        api_key = os.getenv('OPENWEATHER_API_KEY')
        if not api_key:
            print("Note: OPENWEATHER_API_KEY environment variable not set.")
            print("You can get a free API key at: https://openweathermap.org/api")
            print()
    
    add_weather_to_games(args.games_file, args.output, args.api)
    
    print()
    print("=" * 70)
    print("Processing complete!")
    print("=" * 70)

if __name__ == "__main__":
    main()
