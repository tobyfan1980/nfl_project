"""
Weather Data Crawler
Fetches historical weather data from NOAA NCEI API for all days in 2024
"""

import requests
import pandas as pd
from datetime import datetime, timedelta
import time
import argparse

# NOAA NCEI API endpoint
NOAA_API_BASE = "https://www.ncei.noaa.gov/access/services/data/v1"

# Common city to station ID mappings
CITY_STATION_MAP = {
    'seattle': 'USW00024233',  # Seattle-Tacoma International Airport
    'new york': 'USW00094728',  # New York Central Park
    'los angeles': 'USW00023174',  # Los Angeles International Airport
    'chicago': 'USW00094846',  # Chicago O'Hare International Airport
    'houston': 'USW00012918',  # Houston Intercontinental Airport
    'phoenix': 'USW00023183',  # Phoenix Sky Harbor International Airport
    'philadelphia': 'USW00013739',  # Philadelphia International Airport
    'san antonio': 'USW00012953',  # San Antonio International Airport
    'san diego': 'USW00023188',  # San Diego International Airport
    'dallas': 'USW00013960',  # Dallas/Fort Worth International Airport
}

def fetch_weather_data(start_date, end_date, station_id):
    """
    Fetch weather data from NOAA API for a given date range.
    
    Args:
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        station_id: NOAA weather station ID
    
    Returns:
        List of dictionaries containing weather data
    """
    params = {
        'dataset': 'daily-summaries',
        'stations': station_id,
        'startDate': start_date,
        'endDate': end_date,
        'dataTypes': 'TMAX,WT01,WT02,WT03,WT04,WT05,WT06,WT08,WT09,WT11,WT13,WT14,WT15,WT16,WT17,WT18,WT19,WT21,WT22',
        'format': 'json',
        'units': 'standard'
    }
    
    print(f"Fetching weather data from {start_date} to {end_date}...")
    
    try:
        response = requests.get(NOAA_API_BASE, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        if not data:
            print(f"Warning: No data returned for {start_date} to {end_date}")
            return []
        
        print(f"Successfully fetched {len(data)} records")
        return data
    
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data: {e}")
        return []

def parse_weather_condition(row):
    """
    Parse weather condition from NOAA weather type codes.
    WT01-WT22 represent different weather conditions.
    
    Args:
        row: Dictionary containing weather data row
    
    Returns:
        String describing weather condition
    """
    conditions = []
    
    # Weather type codes mapping
    weather_types = {
        'WT01': 'Fog',
        'WT02': 'Heavy Fog',
        'WT03': 'Thunder',
        'WT04': 'Ice Pellets',
        'WT05': 'Hail',
        'WT06': 'Glaze or Rime',
        'WT08': 'Smoke or Haze',
        'WT09': 'Blowing or Drifting Snow',
        'WT11': 'High or Damaging Winds',
        'WT13': 'Mist',
        'WT14': 'Drizzle',
        'WT15': 'Freezing Drizzle',
        'WT16': 'Rain',
        'WT17': 'Freezing Rain',
        'WT18': 'Snow',
        'WT19': 'Unknown Precipitation',
        'WT21': 'Ground Fog',
        'WT22': 'Ice Fog'
    }
    
    for code, condition in weather_types.items():
        if code in row and row[code] and row[code] != '0':
            conditions.append(condition)
    
    if not conditions:
        return 'Clear'
    
    return ', '.join(conditions)

def process_weather_data(raw_data, city_name):
    """
    Process raw weather data and extract relevant fields.
    
    Args:
        raw_data: List of dictionaries from NOAA API
        city_name: Name of the city
    
    Returns:
        List of processed dictionaries
    """
    processed_data = []
    
    for row in raw_data:
        date = row.get('DATE', '')
        tmax = row.get('TMAX', '')
        
        # Convert temperature from tenths of degrees C to Fahrenheit
        # TMAX is in tenths of degrees Celsius
        if tmax and tmax != '':
            try:
                temp_c = float(tmax) / 10.0
                temp_f = (temp_c * 9/5) + 32
                high_temp = round(temp_f, 1)
            except (ValueError, TypeError):
                high_temp = None
        else:
            high_temp = None
        
        condition = parse_weather_condition(row)
        
        processed_data.append({
            'City': city_name,
            'Date': date,
            'High Temperature (°F)': high_temp,
            'Condition': condition
        })
    
    return processed_data

def get_all_2024_data(city_name, station_id):
    """
    Fetch weather data for all days in 2024.
    Splits into monthly requests to avoid API limits.
    
    Args:
        city_name: Name of the city
        station_id: NOAA weather station ID
    
    Returns:
        List of processed weather records
    """
    all_data = []
    
    # Fetch data month by month to be respectful to the API
    months = [
        ('2024-01-01', '2024-01-31'),
        ('2024-02-01', '2024-02-29'),
        ('2024-03-01', '2024-03-31'),
        ('2024-04-01', '2024-04-30'),
        ('2024-05-01', '2024-05-31'),
        ('2024-06-01', '2024-06-30'),
        ('2024-07-01', '2024-07-31'),
        ('2024-08-01', '2024-08-31'),
        ('2024-09-01', '2024-09-30'),
        ('2024-10-01', '2024-10-31'),
        ('2024-11-01', '2024-11-30'),
        ('2024-12-01', '2024-12-31'),
    ]
    
    for start_date, end_date in months:
        raw_data = fetch_weather_data(start_date, end_date, station_id)
        if raw_data:
            processed = process_weather_data(raw_data, city_name)
            all_data.extend(processed)
        
        # Be respectful to the API - small delay between requests
        time.sleep(1)
    
    return all_data

def get_station_id(city_name):
    """
    Get station ID for a given city name.
    
    Args:
        city_name: Name of the city (case-insensitive)
    
    Returns:
        Station ID string, or None if not found
    """
    city_lower = city_name.lower().strip()
    return CITY_STATION_MAP.get(city_lower)

def main():
    """
    Main function to fetch weather data and save to CSV.
    """
    parser = argparse.ArgumentParser(
        description='Fetch historical weather data from NOAA NCEI API for 2024'
    )
    parser.add_argument(
        '--city',
        type=str,
        default='seattle',
        help='City name (default: seattle). Supported cities: seattle, new york, los angeles, chicago, houston, phoenix, philadelphia, san antonio, san diego, dallas. Or provide a custom station ID with --station-id.'
    )
    parser.add_argument(
        '--station-id',
        type=str,
        default=None,
        help='Custom NOAA weather station ID (optional, overrides city lookup)'
    )
    
    args = parser.parse_args()
    
    city_name = args.city.title()  # Capitalize city name for display
    station_id = args.station_id
    
    # If no custom station ID provided, look it up
    if not station_id:
        station_id = get_station_id(args.city)
        if not station_id:
            print(f"Error: City '{args.city}' not found in station mapping.")
            print(f"Available cities: {', '.join(CITY_STATION_MAP.keys())}")
            print("Or provide a custom station ID using --station-id")
            return
    
    print("=" * 60)
    print(f"Weather Data Crawler - {city_name} - 2024")
    print(f"Station ID: {station_id}")
    print("=" * 60)
    print()
    
    # Fetch all data for 2024
    weather_data = get_all_2024_data(city_name, station_id)
    
    if not weather_data:
        print("Error: No weather data was retrieved.")
        return
    
    # Create DataFrame
    df = pd.DataFrame(weather_data)
    
    # Sort by date
    df['Date'] = pd.to_datetime(df['Date'])
    df = df.sort_values('Date')
    df['Date'] = df['Date'].dt.strftime('%Y-%m-%d')
    
    # Reorder columns: City, Date, High Temperature, Condition
    df = df[['City', 'Date', 'High Temperature (°F)', 'Condition']]
    
    # Save to CSV
    city_filename = args.city.lower().replace(' ', '_')
    output_file = f'{city_filename}_weather_2024.csv'
    df.to_csv(output_file, index=False)
    
    print()
    print("=" * 60)
    print(f"Successfully saved {len(df)} records to {output_file}")
    print("=" * 60)
    print()
    print("Sample data:")
    print(df.head(10).to_string(index=False))
    print()
    print(f"Data saved to: {output_file}")

if __name__ == "__main__":
    main()

