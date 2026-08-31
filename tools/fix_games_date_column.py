"""
Fix Date column in games CSV when it contains "boxscore" (scraper artifact).
Derives date from Year, Week, and Day using NFL season calendar.
"""

import csv
import os
from datetime import datetime, timedelta

# Week 1 Thursday game date (opening night) per season
WEEK1_THURSDAY = {
    2022: datetime(2022, 9, 8),
    2023: datetime(2023, 9, 7),
    2024: datetime(2024, 9, 5),
}

DAY_OFFSET = {
    "Thu": 0,
    "Fri": 1,
    "Sat": 2,
    "Sun": 3,
    "Mon": 4,
}


def date_from_week_day(year: int, week: int, day: str) -> str:
    """Return YYYY-MM-DD for the given year, week number (1-18), and day abbrev."""
    if year not in WEEK1_THURSDAY or day not in DAY_OFFSET:
        return ""
    base = WEEK1_THURSDAY[year]
    # Week N: N-1 weeks after Week 1 Thursday
    d = base + timedelta(weeks=week - 1) + timedelta(days=DAY_OFFSET[day])
    return d.strftime("%Y-%m-%d")


def fix_dates_in_games_csv(path: str, year: int) -> None:
    """In-place: replace Date column value when it is 'boxscore' with derived date."""
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames)
        date_col = "Date"
        # Handle duplicate 'Date' column (second one may become Date.1 in some readers)
        date_idx = next((i for i, n in enumerate(fieldnames) if n == date_col), None)
        if date_idx is None:
            print(f"No 'Date' column in {path}")
            return
        for row in reader:
            if row.get(date_col) == "boxscore":
                try:
                    w = int(row["Week"])
                    day = (row.get("Day") or "").strip()
                    row[date_col] = date_from_week_day(year, w, day) or row[date_col]
                except (ValueError, KeyError):
                    pass
            rows.append(row)

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Fix Date column (boxscore -> YYYY-MM-DD) in games CSV")
    parser.add_argument("--games-file", default="dev_data/games/2023_games.csv", help="Path to games CSV")
    parser.add_argument("--year", type=int, default=2023, help="Season year (e.g. 2023)")
    args = parser.parse_args()
    fix_dates_in_games_csv(args.games_file, args.year)
    print(f"Updated dates in {args.games_file} for year {args.year}")


if __name__ == "__main__":
    main()
