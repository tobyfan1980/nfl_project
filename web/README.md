# Hot Hand predictions site

`docs/index.html` is a single static page served by GitHub Pages. It shows this
week's picks, the season record, and every past pick graded against the final
score.

## Weekly update (Tuesday night, Pacific)

Run from the repository root after Monday Night Football is final:

```bash
python tools/weekly_update.py
git add dev_data/games/2026_schedule.csv dev_data/predictions docs
git commit -m "week N picks"
git push
```

The script:

1. Downloads the season's schedule and scores from nflverse
   (`https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv`)
   into `dev_data/games/{season}_schedule.csv`.
2. Picks the next week to predict: the first week with unplayed games. It
   refuses if any earlier game is not final yet (for example, running before
   MNF ends); re-run later.
3. Saves that week's picks to `dev_data/predictions/{season}/week_NN.json`,
   using results from earlier weeks only.
4. Rebuilds `docs/index.html` from the saved pick files and the latest scores.

Useful flags: `--week N` to choose the week, `--offline` to reuse the saved
schedule without downloading, `--season YYYY` for another season. A saved week
is never overwritten unless you pass `--force`.

## Why picks are saved

The history on the site reads only the saved `week_NN.json` files and grades
them with the latest scores. Past picks are never recomputed, so the record is
exactly what was predicted before each week. Don't edit or `--force` a week
after its games start.

## Pick file format

```json
{
  "season": 2026,
  "week": 6,
  "generated_at": "2026-10-17T14:02-0700",
  "features_through_week": 5,
  "model": {"name": "last5-logistic-v1", "intercept": 0.3271, "slope": 1.8526, "trained_on": "..."},
  "data_source": "<nflverse URL>",
  "games_final_before_prediction": ["2026_06_SEA_DEN"],
  "games": [{
    "game_id": "2026_06_HOU_JAX",
    "kickoff_pt": "2026-10-18T06:30-0700",
    "location": "Neutral",
    "home": "JAX", "away": "HOU",
    "home_last5": {"games": 5, "wins": 4, "losses": 1, "ties": 0, "win_rate": 0.8},
    "away_last5": {"games": 5, "wins": 1, "losses": 4, "ties": 0, "win_rate": 0.2},
    "home_win_prob": 0.8082,
    "pick": "JAX"
  }]
}
```

Teams use nflverse abbreviations (`LA` is the Rams).

## Model

`tools/nfl_model.py` holds the logistic fit from `project_log/2026_09_07.md`
(trained on 2022-2024):

```
P(home win) = 1 / (1 + e^-(0.3271 + 1.8526 * (home_last5_win_rate - away_last5_win_rate)))
```

The last-5 win rate matches `plugins/nfl-previous-five-win-rate`: the team's
last five games this season, ties count as half. Run on the 2025 schedule, this
code reproduces the committed 2025 features for all 194 games and the 69.6%
hold-out accuracy.

## Editing the page

Markup, styles and rendering code live in `web/template.html`;
`tools/build_site.py` injects the data at `/*__SITE_DATA__*/null`. Edit the
template, then run `python tools/build_site.py --season 2026`. Don't edit
`docs/index.html` by hand; it is generated.

## Hosting

In repository Settings -> Pages, set Source to "Deploy from a branch", branch
`main`, folder `/docs`. The site is then at
`https://tobyfan1980.github.io/nfl_project/`.
