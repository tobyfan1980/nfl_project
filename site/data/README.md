# PocketPicks data contract

Every file in this directory is plain JSON that the Python pipeline
(`site_scripts/`) writes and the static pages read. The fixtures committed
here are hand-written, internally consistent examples; they are also pinned
by `site_scripts/tests/test_data_contract.py`. Other tasks cite this file as
the authoritative shape.

Conventions used throughout:

- Probabilities, win rates and accuracy `pct` values are fractions in
  `[0, 1]` (for example `0.78`), not percentages. The UI formats them.
- Timestamps are ISO 8601 UTC strings ending in `Z`.
- `"home"` / `"away"` are the only side markers.
- Slugs are lowercase team abbreviations (`kc`, `den`) and match the file
  names in `assets/img/teams/`.

## Game id

```
{season}-W{week:02d}-{home_slug}-{away_slug}
```

Lowercase slugs, home team first. Example: `2026-W07-kc-den` is Denver at
Kansas City.

## `season.json`

```json
{"season": 2026, "current_week": 7, "model_active_from_week": 2}
```

`model_active_from_week` is the first week with predictions (needs at
least one prior game per team; the rate uses up to five). Earlier weeks have `prediction: null`.

## `week_NN.json`

```json
{
  "season": 2026,
  "week": 7,
  "generated_at": "2026-10-14T10:12:00Z",
  "games": [Game, ...]
}
```

`Game`:

```json
{
  "id": "2026-W07-kc-den",
  "kickoff_utc": "2026-10-19T17:00:00Z",
  "home": Team,
  "away": Team,
  "prediction": Prediction | null,
  "odds": Odds | null,
  "last5_home": [Result, ...],
  "last5_away": [Result, ...]
}
```

`last5_home` / `last5_away` hold at most 5 `Result` entries (fewer early in
the season), most recent first.

`Team`:

```json
{"team": "Kansas City Chiefs", "slug": "kc", "record": "5-1", "streak": "W3"}
```

`Prediction` (`null` when the model is not active, i.e. Weeks 1-5):

```json
{
  "home_win_prob": 0.74,
  "away_win_prob": 0.26,
  "favored": "home",
  "home_last5_win_rate": 0.80,
  "away_last5_win_rate": 0.40,
  "diff": 0.40,
  "model": "logistic_v1 (0.3271 + 1.8526 * diff)"
}
```

`diff = home_last5_win_rate - away_last5_win_rate`;
`logit P(home_win) = 0.3271 + 1.8526 * diff`; `favored` is the side with
the larger probability; the two probabilities sum to 1.

`Odds` (`null` when no odds API key or no line for the game):

```json
{
  "home_moneyline": -340,
  "away_moneyline": 270,
  "books": 9,
  "source": "the-odds-api",
  "pulled_at": "2026-10-14T10:11:50Z"
}
```

Moneylines are the median across `books` US bookmakers.

`Result` (one past game for the team in question):

```json
{"opponent": "lv", "result": "W", "score": "27-20", "home_away": "home"}
```

`opponent` is the opponent's lowercase slug; `result` is `"W"`, `"L"` or `"T"`; `score` is `"<team points>-<opponent
points>"` from the perspective of the team whose list it is in;
`home_away` is where that team played.

## `results.json`

Keyed by game id. Written when games finish; never rewritten for earlier
predictions.

```json
{
  "2026-W07-kc-den": {
    "season": 2026,
    "week": 7,
    "final": "27-20",
    "winner": "home",
    "picked": "home",
    "correct": true
  }
}
```

`final` is `"<home points>-<away points>"`. `picked` is `"home"`, `"away"`
or `null` (no prediction was made); `correct` is a boolean, or `null` when
`picked` is `null`. `correct` is `true` exactly when `picked == winner`.
Games with `correct: null` are excluded from every accuracy total.

## `accuracy.json`

Recomputed from scratch from `results.json` on every run.

```json
{
  "season": 2026,
  "weeks": [
    {
      "week": 6,
      "correct": 3,
      "total": 4,
      "pct": 0.75,
      "cumulative_correct": 3,
      "cumulative_total": 4,
      "cumulative_pct": 0.75
    }
  ],
  "overall": {"correct": 4, "total": 6, "pct": 0.6667, "record": "4-2"}
}
```

`total` counts results whose `correct` is not `null`. `pct` is
`correct / total` rounded to 4 decimals. `record` is `"<correct>-<wrong>"`.
`overall` equals the final week's cumulative values.

## `injuries.json`

```json
{
  "available": true,
  "pulled_at": "2026-10-14T10:12:30Z",
  "teams": {
    "kc": [
      {"player": "Isiah Pacheco", "position": "RB", "status": "Questionable", "injury": "Ankle"}
    ]
  }
}
```

When the report could not be fetched (robots.txt disallowed, request
failed) the file is:

```json
{"available": false, "pulled_at": "2026-10-14T10:12:30Z", "reason": "robots.txt disallows fetch", "teams": {}}
```

`reason` is only present when `available` is `false`. `status` is one of
`Out`, `Doubtful`, `Questionable`.
