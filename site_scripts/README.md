# PocketPicks site scripts

Python pipeline behind the PocketPicks GitHub Pages site. **`update_week.py`
does the prediction AND writes the page data** (`site/data/*.json`); **pushing
to GitHub is what updates the live site.** Nothing is published until you
commit and push.

## Setup

```sh
pip install -r requirements.txt pytest
python3 -m pytest site_scripts/tests/ -v      # sanity check (no network needed)
```

Optional, for moneyline odds on each game: put a free
[the-odds-api.com](https://the-odds-api.com) key in `~/.pocketpicks_odds_key`
(file contents = the key only). The file lives outside the repo on purpose.
Without it the script still runs and every game just has `odds: null`.

## Weekly update (every Tuesday)

```sh
python site_scripts/update_week.py --season <YEAR> --week <WEEK>
# e.g. python site_scripts/update_week.py --season 2026 --week 7
```

`--week` is the UPCOMING week to publish. The script then:

1. crawls last week's finished games into `dev_data/games/<YEAR>_games.csv`
   (skip with `--skip-ingest` if they are already there),
2. regenerates the metric CSVs in `dev_data/metrics/`,
3. scores last week's stored picks into `site/data/results.json` and
   recomputes `site/data/accuracy.json`,
4. fetches the upcoming schedule, predicts every game from the two teams'
   last-5 win rates (a team with fewer than 5 prior games gives
   `prediction: null`, i.e. "warming up"), attaches odds,
5. fetches the injury report, and
6. writes `week_NN.json`, `results.json`, `accuracy.json`, `injuries.json` and
   `season.json` (`current_week` = the week you ran) to `site/data/`
   (override with `--data-dir`).

Re-running the same season/week is safe: the output is rebuilt from the same
inputs, and unchanged files are left untouched.

## Publish

```sh
git add site/data && git commit -m "Week 7 update" && git push
```

The push is the publish step: GitHub Pages serves whatever is on the branch.
Running the script alone changes only your local files.

## Notes and known gaps

- **Travel-timezone metrics** need a stadium-locations reference file that is
  not in the repo. That generator is best-effort: its failure is logged and
  skipped. The site does not use it (only the last-5 win rate drives the
  prediction), so nothing on the site is affected.
- `record`, `streak` and the `last5_*` lists are derived from the season games
  CSV using only games from weeks before `--week`. A team with no games yet
  shows `0-0` / `W0`. Neutral-site games are not marked in the crawler data,
  so they are labelled with the winner as "home".
- A game that nflverse lists with no kickoff time yet is skipped (with a
  warning) rather than aborting the week; it appears once a time is set.
