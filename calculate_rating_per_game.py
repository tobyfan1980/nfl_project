"""
Calculate offensive and defensive ratings per game from 2022 NFL games data.
Reads 2022_games.csv and outputs 2022_game_ratings.csv with ratings for each team per game.
"""

import csv
import os
from model import NFLModel1

def read_and_calculate_ratings(input_file: str, output_file: str):
    """
    Read game data from CSV file and calculate offensive/defensive ratings for each team.
    
    Args:
        input_file: Path to input CSV file (2022_games.csv)
        output_file: Path to output CSV file (2022_game_ratings.csv)
    """
    # Initialize the model
    model = NFLModel1()
    results = []
    
    with open(input_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            # Skip empty rows or playoff header rows
            if not row.get('Winner/tie') or not row.get('Loser/tie'):
                continue
            
            # Extract fields
            winner_team = row['Winner/tie'].strip()
            loser_team = row['Loser/tie'].strip()
            
            # Check for '@' in the empty column between Winner/tie and Loser/tie
            # The '@' indicates the winner is away
            # Check all values in the row for '@' symbol
            has_at_symbol = any('@' in str(value) for value in row.values())
            
            # Determine home/away
            # If '@' is present: winner is Away, loser is Home
            # If '@' is not present: winner is Home, loser is Away
            if has_at_symbol:
                winner_home_away = 'Away'
                loser_home_away = 'Home'
            else:
                winner_home_away = 'Home'
                loser_home_away = 'Away'
            
            try:
                winner_score = int(row['PtsW'])
                loser_score = int(row['PtsL'])
                winner_yards = int(row['YdsW'])
                loser_yards = int(row['YdsL'])
                winner_turnovers = int(row['TOW'])
                loser_turnovers = int(row['TOL'])
            except (ValueError, KeyError) as e:
                print(f"Warning: Skipping row due to missing/invalid data: {e}")
                continue
            
            # Calculate offensive rating for winner (using winner's yards and points)
            winner_off_rating = model.offensive_rating(winner_yards, winner_score)
            
            # Calculate defensive rating for winner (using loser's yards, points, and turnovers)
            winner_def_rating = model.defensive_rating(loser_yards, loser_score, loser_turnovers)
            
            # Calculate offensive rating for loser (using loser's yards and points)
            loser_off_rating = model.offensive_rating(loser_yards, loser_score)
            
            # Calculate defensive rating for loser (using winner's yards, points, and turnovers)
            loser_def_rating = model.defensive_rating(winner_yards, winner_score, winner_turnovers)
            
            # Add winner row
            results.append({
                'team': winner_team,
                'score': winner_score,
                'win_lose': 'W',
                'home_away': winner_home_away,
                'offensive_rating': round(winner_off_rating, 3),
                'defensive_rating': round(winner_def_rating, 3)
            })
            
            # Add loser row
            results.append({
                'team': loser_team,
                'score': loser_score,
                'win_lose': 'L',
                'home_away': loser_home_away,
                'offensive_rating': round(loser_off_rating, 3),
                'defensive_rating': round(loser_def_rating, 3)
            })
    
    # Create output directory if it doesn't exist
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    # Write results to output CSV
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        fieldnames = ['team', 'score', 'win_lose', 'home_away', 'offensive_rating', 'defensive_rating']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        
        writer.writeheader()
        writer.writerows(results)
    
    print(f"Successfully processed {len(results)} team-game records")
    print(f"Results saved to {output_file}")
    print(f"Total games processed: {len(results) // 2}")

def main():
    """Main function to run the rating calculation."""
    input_file = 'dev_data/2022_games.csv'
    output_file = 'dev_data/2022_game_ratings.csv'
    
    print("=" * 70)
    print("NFL Game Ratings Calculator")
    print("=" * 70)
    print()
    print(f"Reading from: {input_file}")
    print(f"Writing to: {output_file}")
    print()
    
    read_and_calculate_ratings(input_file, output_file)
    
    print()
    print("=" * 70)
    print("Processing complete!")
    print("=" * 70)

if __name__ == "__main__":
    main()
