"""PocketPicks accuracy tallies, recomputed from scratch from results.json.

Only results with a non-null ``correct`` (i.e. a real pick was made) count.
``overall`` is derived from the same per-week rows that are returned, so
``overall == sum(weeks)`` holds by construction (the history-page invariant).
"""


def _pct(correct: int, total: int) -> float:
    """Fraction rounded to 4 dp; 0.0 when there are no counted games."""
    return round(correct / total, 4) if total else 0.0


def compute_accuracy(results: dict, season: int) -> dict:
    """Build the accuracy.json body for ``season`` from a results dict."""
    per_week: dict[int, list[int]] = {}  # week -> [correct, total]
    for r in results.values():
        if r.get("season") != season or r.get("correct") is None:
            continue
        tally = per_week.setdefault(r["week"], [0, 0])
        tally[0] += 1 if r["correct"] else 0
        tally[1] += 1

    weeks = []
    cum_correct = cum_total = 0
    for week in sorted(per_week):
        correct, total = per_week[week]
        cum_correct += correct
        cum_total += total
        weeks.append({
            "week": week,
            "correct": correct,
            "total": total,
            "pct": _pct(correct, total),
            "cumulative_correct": cum_correct,
            "cumulative_total": cum_total,
            "cumulative_pct": _pct(cum_correct, cum_total),
        })

    overall = {
        "correct": cum_correct,
        "total": cum_total,
        "pct": _pct(cum_correct, cum_total),
        "record": f"{cum_correct}-{cum_total - cum_correct}",
    }
    return {"season": season, "weeks": weeks, "overall": overall}
