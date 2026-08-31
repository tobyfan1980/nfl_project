#!/usr/bin/env python3
"""Prepare deterministic chart data from an NFL travel-timezone CSV."""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter, defaultdict
from pathlib import Path


METRICS = (
    "timezone-transition-distribution",
    "travel-miles-histogram",
    "log-travel-miles-histogram",
    "average-travel-by-team",
)
REQUIRED_COLUMNS = {"team", "travel_miles", "timezone_transition_hours"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-file", type=Path, required=True)
    parser.add_argument("--metric", choices=METRICS, required=True)
    parser.add_argument("--bins", type=int, default=12)
    parser.add_argument("--output-file", type=Path)
    args = parser.parse_args()
    if args.bins < 1:
        parser.error("--bins must be at least 1")
    return args


def parse_number(value: str, column: str, row_number: int) -> float:
    try:
        return float(value)
    except ValueError as exc:
        raise ValueError(f"row {row_number}: invalid {column} value {value!r}") from exc


def load_records(input_file: Path) -> list[dict[str, float | str]]:
    if not input_file.exists():
        raise FileNotFoundError(f"input file not found: {input_file}")

    records: list[dict[str, float | str]] = []
    with input_file.open(newline="", encoding="utf-8") as source:
        reader = csv.DictReader(source)
        if not reader.fieldnames:
            raise ValueError(f"input file is empty: {input_file}")
        missing_columns = REQUIRED_COLUMNS - set(reader.fieldnames)
        if missing_columns:
            missing = ", ".join(sorted(missing_columns))
            raise ValueError(f"input file is missing required columns: {missing}")

        for row_number, row in enumerate(reader, start=2):
            team = row["team"].strip()
            if not team:
                raise ValueError(f"row {row_number}: team is empty")
            travel_miles = parse_number(row["travel_miles"], "travel_miles", row_number)
            timezone_hours = parse_number(
                row["timezone_transition_hours"], "timezone_transition_hours", row_number
            )
            if travel_miles < 0:
                raise ValueError(f"row {row_number}: travel_miles cannot be negative")
            records.append(
                {
                    "team": team,
                    "travel_miles": travel_miles,
                    "timezone_transition_hours": timezone_hours,
                }
            )
    if not records:
        raise ValueError(f"input file has no data rows: {input_file}")
    return records


def display_number(value: float) -> int | float:
    return int(value) if value.is_integer() else value


def histogram(values: list[float], bins: int) -> list[dict[str, float | int]]:
    if not values:
        return []
    lower, upper = min(values), max(values)
    if math.isclose(lower, upper):
        return [{"start": lower, "end": upper + 1.0, "count": len(values)}]

    width = (upper - lower) / bins
    counts = [0] * bins
    for value in values:
        index = min(int((value - lower) / width), bins - 1)
        counts[index] += 1
    return [
        {
            "start": round(lower + index * width, 6),
            "end": round(lower + (index + 1) * width, 6),
            "count": count,
        }
        for index, count in enumerate(counts)
    ]


def build_payload(
    records: list[dict[str, float | str]], metric: str, bins: int, input_file: Path
) -> dict[str, object]:
    payload: dict[str, object] = {
        "metric": metric,
        "source_file": str(input_file),
        "record_count": len(records),
    }
    travel_miles = [float(record["travel_miles"]) for record in records]

    if metric == "timezone-transition-distribution":
        counts = Counter(float(record["timezone_transition_hours"]) for record in records)
        payload["x_label"] = "Timezone transition hours"
        payload["y_label"] = "Team-games"
        payload["data"] = [
            {"hours": display_number(hours), "count": counts[hours]}
            for hours in sorted(counts)
        ]
        return payload

    if metric == "travel-miles-histogram":
        payload["x_label"] = "Travel miles"
        payload["y_label"] = "Team-games"
        payload["data"] = histogram(travel_miles, bins)
        return payload

    if metric == "log-travel-miles-histogram":
        positive_logs = [math.log1p(miles) for miles in travel_miles if miles > 0]
        payload["transform"] = "ln(1 + travel_miles)"
        payload["x_label"] = "ln(1 + travel miles)"
        payload["y_label"] = "Team-games"
        payload["zero_count"] = sum(miles == 0 for miles in travel_miles)
        payload["data"] = histogram(positive_logs, bins)
        return payload

    totals: defaultdict[str, list[float]] = defaultdict(list)
    for record in records:
        totals[str(record["team"])].append(float(record["travel_miles"]))
    payload["x_label"] = "Average travel miles per game"
    payload["y_label"] = "Team"
    payload["data"] = [
        {
            "team": team,
            "average_travel_miles": round(sum(miles) / len(miles), 3),
            "games": len(miles),
        }
        for team, miles in sorted(
            totals.items(), key=lambda item: sum(item[1]) / len(item[1]), reverse=True
        )
    ]
    return payload


def main() -> int:
    args = parse_args()
    payload = build_payload(load_records(args.input_file), args.metric, args.bins, args.input_file)
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
