"""
Add zipcode column to NFL games CSV file.
Reads team-zipcode mapping from nfl_teams_stadium_zip_only.csv and adds zipcode
for the home team in each game row.
"""

import csv
import os

def load_team_zipcode_mapping(zipcode_file: str) -> dict:
    """
    Load team name to zipcode mapping from CSV file.
    
    Args:
        zipcode_file: Path to nfl_teams_stadium_zip_only.csv
        
    Returns:
        Dictionary mapping team names to zipcodes
    """
    team_zipcode = {}
    
    with open(zipcode_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            team_name = row['Team'].strip()
            zipcode = row['Stadium ZIP Code'].strip()
            team_zipcode[team_name] = zipcode
    
    return team_zipcode

def determine_home_team(row: dict) -> str:
    """
    Determine which team is the home team based on the '@' symbol.
    
    Args:
        row: Dictionary representing a game row
        
    Returns:
        Name of the home team
    """
    winner = row['Winner/tie'].strip()
    loser = row['Loser/tie'].strip()
    
    # Check if '@' symbol is present in any column value
    has_at_symbol = any('@' in str(value) for value in row.values())
    
    # If '@' is present: winner is Away, loser is Home
    # If '@' is not present: winner is Home, loser is Away
    if has_at_symbol:
        return loser
    else:
        return winner

def add_zipcodes_to_games(games_file: str, zipcode_file: str, output_file: str = None):
    """
    Add zipcode column to games CSV file based on home team.
    
    Args:
        games_file: Path to games CSV file (e.g., 2023_games.csv)
        zipcode_file: Path to team-zipcode mapping file
        output_file: Path to output file (if None, overwrites input file)
    """
    # Load team to zipcode mapping
    print(f"Loading team-zipcode mapping from {zipcode_file}...")
    team_zipcode = load_team_zipcode_mapping(zipcode_file)
    print(f"Loaded {len(team_zipcode)} team mappings")
    
    # Read games file and add zipcodes
    rows = []
    missing_teams = set()
    
    print(f"\nReading games from {games_file}...")
    with open(games_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        
        # Add 'zipcode' column if it doesn't exist
        if 'zipcode' not in fieldnames:
            fieldnames = list(fieldnames) + ['zipcode']
        
        for row in reader:
            # Skip empty rows
            if not row.get('Winner/tie') or not row.get('Loser/tie'):
                rows.append(row)
                continue
            
            # Determine home team
            home_team = determine_home_team(row)
            
            # Look up zipcode
            zipcode = team_zipcode.get(home_team, '')
            if not zipcode:
                missing_teams.add(home_team)
            
            # Add zipcode to row
            row['zipcode'] = zipcode
            rows.append(row)
    
    # Write updated data
    if output_file is None:
        output_file = games_file
    
    print(f"\nWriting updated data to {output_file}...")
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    
    print(f"Successfully processed {len(rows)} rows")
    
    if missing_teams:
        print(f"\nWarning: Could not find zipcode for {len(missing_teams)} team(s):")
        for team in sorted(missing_teams):
            print(f"  - {team}")
    else:
        print("\nAll teams matched successfully!")

def main():
    """Main function to add zipcodes to games file."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Add zipcode column to NFL games CSV')
    parser.add_argument('--games-file', type=str, 
                       default='dev_data/2023_games.csv',
                       help='Path to games CSV file (default: dev_data/2023_games.csv)')
    parser.add_argument('--zipcode-file', type=str,
                       default='dev_data/nfl_teams_stadium_zip_only_5digit_text.csv',
                       help='Path to team-zipcode mapping file (default: dev_data/nfl_teams_stadium_zip_only_5digit_text.csv)')
    parser.add_argument('--output', type=str, default=None,
                       help='Output file path (default: overwrites input file)')
    
    args = parser.parse_args()
    
    print("=" * 70)
    print("NFL Games Zipcode Adder")
    print("=" * 70)
    print()
    
    add_zipcodes_to_games(args.games_file, args.zipcode_file, args.output)
    
    print()
    print("=" * 70)
    print("Processing complete!")
    print("=" * 70)

if __name__ == "__main__":
    main()

