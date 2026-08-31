#!/usr/bin/env python3
"""Prepare pooled interval-count chart data from NFL game-interval CSV files."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path


REQUIRED_COLUMN = "days_between_games"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-files", nargs="+", type=Path, required=True)
    parser.add_argument("--output-file", type=Path)
    return parser.parse_args()


def load_intervals(input_files: list[Path]) -> tuple[list[int], list[str]]:
    intervals: list[int] = []
    years: list[str] = []
    for input_file in input_files:
        if not input_file.exists():
            raise FileNotFoundError(f"input file not found: {input_file}")
        prefix = input_file.name.removesuffix("_game_intervals.csv")
        if prefix.isdigit() and len(prefix) == 4:
            years.append(prefix)

        with input_file.open(newline="", encoding="utf-8") as source:
            reader = csv.DictReader(source)
            if not reader.fieldnames:
                raise ValueError(f"input file is empty: {input_file}")
            if REQUIRED_COLUMN not in reader.fieldnames:
                raise ValueError(
                    f"input file is missing required column {REQUIRED_COLUMN}: {input_file}"
                )
            for row_number, row in enumerate(reader, start=2):
                try:
                    interval = int(row[REQUIRED_COLUMN])
                except ValueError as exc:
                    raise ValueError(
                        f"{input_file} row {row_number}: invalid {REQUIRED_COLUMN} value "
                        f"{row[REQUIRED_COLUMN]!r}"
                    ) from exc
                if interval < 0:
                    raise ValueError(
                        f"{input_file} row {row_number}: {REQUIRED_COLUMN} cannot be negative"
                    )
                intervals.append(interval)
    if not intervals:
        raise ValueError("input files have no interval rows")
    return intervals, sorted(set(years))


def build_payload(intervals: list[int], years: list[str], input_files: list[Path]) -> dict[str, object]:
    counts = Counter(intervals)
    return {
        "source_files": [str(input_file) for input_file in input_files],
        "years": years,
        "record_count": len(intervals),
        "x_label": "Days between previous and current game",
        "y_label": "Team-games",
        "data": [
            {"days": day, "count": counts[day]}
            for day in range(min(counts), max(counts) + 1)
        ],
    }


def main() -> int:
    args = parse_args()
    intervals, years = load_intervals(args.input_files)
    payload = build_payload(intervals, years, args.input_files)
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
