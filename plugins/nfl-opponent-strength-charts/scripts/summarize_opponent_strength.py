#!/usr/bin/env python3
"""Prepare season histogram data from NFL opponent-strength CSV files."""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from pathlib import Path


REQUIRED_COLUMN = "opponent_strength_average_win_rate"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-files", nargs="+", type=Path, required=True)
    parser.add_argument("--bins", type=int, default=20)
    parser.add_argument("--output-file", type=Path)
    args = parser.parse_args()
    if not 1 <= args.bins <= 100:
        parser.error("--bins must be between 1 and 100")
    return args


def season_from_path(path: Path) -> str:
    season = path.name.removesuffix("_opp_strength.csv")
    if len(season) != 4 or not season.isdigit():
        raise ValueError(f"expected filename yyyy_opp_strength.csv: {path}")
    return season


def load_values(path: Path) -> list[float]:
    if not path.exists():
        raise FileNotFoundError(f"input file not found: {path}")

    values: list[float] = []
    with path.open(newline="", encoding="utf-8") as source:
        reader = csv.DictReader(source)
        if not reader.fieldnames:
            raise ValueError(f"input file is empty: {path}")
        if REQUIRED_COLUMN not in reader.fieldnames:
            raise ValueError(f"{path} is missing required column {REQUIRED_COLUMN}")
        for row_number, row in enumerate(reader, start=2):
            try:
                value = float(row[REQUIRED_COLUMN])
            except ValueError as exc:
                raise ValueError(
                    f"{path} row {row_number}: invalid {REQUIRED_COLUMN} value "
                    f"{row[REQUIRED_COLUMN]!r}"
                ) from exc
            if not math.isfinite(value) or not 0.0 <= value <= 1.0:
                raise ValueError(
                    f"{path} row {row_number}: {REQUIRED_COLUMN} must be within [0, 1]"
                )
            values.append(value)
    if not values:
        raise ValueError(f"input file has no data rows: {path}")
    return values


def histogram(values: list[float], bins: int) -> list[dict[str, float | int]]:
    counts = [0] * bins
    for value in values:
        index = min(int(value * bins), bins - 1)
        counts[index] += 1
    return [
        {
            "start": round(index / bins, 6),
            "end": round((index + 1) / bins, 6),
            "count": count,
        }
        for index, count in enumerate(counts)
    ]


def build_payload(input_files: list[Path], bins: int) -> dict[str, object]:
    seasons = []
    seen_years: set[str] = set()
    for path in input_files:
        year = season_from_path(path)
        if year in seen_years:
            raise ValueError(f"duplicate season input: {year}")
        seen_years.add(year)
        values = load_values(path)
        seasons.append(
            {
                "year": year,
                "source_file": str(path),
                "record_count": len(values),
                "mean": round(statistics.fmean(values), 6),
                "population_standard_deviation": round(statistics.pstdev(values), 6),
                "minimum": min(values),
                "maximum": max(values),
                "data": histogram(values, bins),
            }
        )

    seasons.sort(key=lambda season: str(season["year"]))
    return {
        "metric": "opponent-strength-win-rate-distribution",
        "domain": [0.0, 1.0],
        "bins": bins,
        "bin_width": round(1 / bins, 6),
        "x_label": "Average opponent win rate",
        "y_label": "Team-game rows",
        "record_count": sum(int(season["record_count"]) for season in seasons),
        "seasons": seasons,
    }


def main() -> int:
    args = parse_args()
    payload = build_payload(args.input_files, args.bins)
    serialized = json.dumps(payload, indent=2)
    if args.output_file:
        args.output_file.parent.mkdir(parents=True, exist_ok=True)
        args.output_file.write_text(serialized + "\n", encoding="utf-8")
        print(f"wrote {args.output_file}")
    else:
        print(serialized)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
