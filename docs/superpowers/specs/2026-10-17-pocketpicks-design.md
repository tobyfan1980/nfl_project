# PocketPicks — Design Document

**Date:** 2026-10-17
**Branch:** `pocketpicks-site`

## Intent

PocketPicks is a public, static website that publishes weekly NFL game
predictions from the model trained in this repository, together with a
historical scoreboard of how the model has performed. It is built and
maintained by a small team of high-schoolers; new predictions ship once a
week by running a single Python script on a laptop and pushing the result.

### Why

The repository already contains:
- A crawler that pulls completed-game stats from Pro Football Reference.
- A metrics pipeline that produces per-game last-5 win rates, travel,
  rest, timezone and schedule-strength features for 2022–2025.
- A trained logistic prediction model with hold-out validation
  (69.6% accuracy on 2025 weeks 6–18).

Everything needed to make a public pick each week exists in the repo but
is not reachable to anyone outside the project. The site is the shortest
path from the work that is already done to a thing people can look at on
a Tuesday morning.

### What success looks like

- Every Tuesday during the regular season, running one script and
  committing the result updates the live site with that week's picks.
- A visitor landing on the homepage immediately sees the upcoming week's
  games with each predicted winner, the model's confidence and the
  bookmaker odds for comparison.
- A visitor can click any game for deeper context (team records,
  streaks, last-5 games, current injury report) and can open a history
  page to see how the model has done each week and overall.
- Hosted on GitHub Pages, zero running services, zero recurring cost.

## Goals

1. Weekly picks for the upcoming NFL week, prominently displayed on the
   homepage.
2. Per-game detail page with records, streaks, last-5 results and current
   injuries.
3. Prediction history by week, with a week selector showing accuracy for
   that week's games and a running tally of per-week and overall
   accuracy across every tracked game.
4. One Python update script, runnable from a laptop, that performs the
   full weekly refresh and produces the data files the static site
   reads.
5. Clear site identity: wordmark + icon logo for **PocketPicks**, email
   contact in the footer.
6. Hosted on GitHub Pages from this repository.

## Non-goals

- A backend, database, user accounts, sign-ups, comments, or any
  interactive feature that requires a server.
- Mobile apps.
- Live in-game score updates.
- Picks for individual player props, point spreads, or over/unders. The
  model predicts the game winner only.
- Automatic scheduled updates. The script runs manually on Tuesdays.
- A second trained model or any change to the current predictor's
  training. The site uses the existing logistic coefficients as-is.

## Anti-goals (would make this a failure even if it technically works)

- The site is slow to load or looks broken on a phone. Visitors on
  mobile should see a clean, usable layout without horizontal scroll.
- A visitor cannot tell what the predicted percentage means or which
  team is favored. The headline number and the favored team must be
  unmistakable at a glance.
- The weekly update takes longer than ~15 minutes of hands-on time, or
  requires editing more than one file by hand. Running one script and
  pushing a commit must be enough.
- The history page shows a tally that disagrees with the per-week
  pages. There is one source of truth per week's results, and both
  views read it.
- The site publishes a prediction that was secretly edited after the
  games were played. All prediction JSON is committed at the time it is
  made and never rewritten retroactively; outcomes are appended to a
  separate results file.

## Constraints

- **Static only.** GitHub Pages serves files, nothing else. All content
  renders from static HTML, CSS, JS and JSON data files committed in
  the repo.
- **Vanilla stack.** HTML, CSS and JavaScript, no framework, no build
  step. One third-party dependency for charts: Chart.js, loaded from
  cdnjs. Matches the house style of `defense-alignment-trainer.html`
  in the user's related project.
- **The predictor is fixed.** Picks come from the trained logistic
  equation documented in `project_log/2026_09_07.md`:
  `logit P(home_win) = 0.3271 + 1.8526 × (home_last5_win_rate − away_last5_win_rate)`
  The site hard-codes those two coefficients. Any retraining is a
  separate project.
- **Weeks 1–5 have no prediction.** The last-5 win rate requires five
  prior games per team; the site displays the schedule for these weeks
  with a short "model warming up" note instead of a percentage.
- **Injury data from `nfl.com/injuries/`.** The update script attempts
  a single respectful fetch of the page, honoring `robots.txt`. If
  `robots.txt` disallows the fetch (or the request fails), the script
  does not scrape and leaves `injuries.json` empty with
  `{"available": false, "reason": "..."}`. In that case the game
  detail page replaces the embedded injury panel with an outbound
  link: "View current injury report at nfl.com/injuries →". The
  script never attempts to work around `robots.txt`.
- **Odds data source.** The update script pulls moneyline odds for each
  upcoming game from `the-odds-api.com` free tier (500 requests/month,
  well under the budget for one Tuesday run per week). This requires a
  free API key, stored in `~/.pocketpicks_odds_key` on the maintainer's
  laptop, never committed. If the key is missing, odds fields in the
  JSON are left blank and the UI gracefully hides the odds row for
  that card. **Builder's call:** the-odds-api returns per-bookmaker
  prices; the script aggregates them as the **median moneyline** across
  all available US bookmakers for each side, and the UI labels the row
  "Consensus (median of N books)" with N shown in a tooltip.
- **Upcoming-game schedule source.** The existing PFR crawler only
  parses completed box scores, so it cannot be reused for the next
  week's unplayed matchups. **Builder's call:** fetch the upcoming
  week's schedule (opponents + kickoff times) from the public
  `nflverse` schedules CSV
  (`https://github.com/nflverse/nfldata/blob/master/data/games.csv`),
  which includes every scheduled game before it is played. The script
  reads the current season's rows for the target week. This is
  friendlier than scraping PFR for unplayed games and the nflverse data
  is updated continuously by its maintainers.
- **GitHub Pages publishing.** Pages' native branch+folder picker only
  supports `/` or `/docs`. **Builder's call:** publish via a GitHub
  Actions workflow at `.github/workflows/pages.yml` that uploads the
  `site/` directory as the Pages artifact on every push to `main`.
  This keeps the folder name honest and does not force a rename to
  `/docs/` (which already holds the design document).
- **No tracking, no cookies, no third-party fonts beyond Google Fonts.**

## How it gets made

### Repository layout

Everything lives inside this repository, on the `pocketpicks-site`
branch.

```
nfl_project/
├── site/                             # the static site (GitHub Pages root)
│   ├── index.html                    # this week's picks
│   ├── game.html                     # single-game detail page
│   ├── history.html                  # prediction history + scoreboard
│   ├── about.html                    # (optional, see below)
│   ├── assets/
│   │   ├── css/styles.css
│   │   ├── js/
│   │   │   ├── common.js             # shared data loading, formatting
│   │   │   ├── home.js
│   │   │   ├── game.js
│   │   │   └── history.js
│   │   ├── img/
│   │   │   ├── logo.svg              # PocketPicks wordmark + icon
│   │   │   ├── favicon.svg
│   │   │   └── teams/                # 32 team logos, SVG, lowercase slug
│   │   └── vendor/
│   │       └── chart.min.js          # Chart.js, pinned version
│   └── data/                         # written by the update script
│       ├── season.json               # season config: year, current week
│       ├── week_01.json … week_18.json
│       ├── results.json              # per-week outcomes once games finish
│       ├── accuracy.json             # pre-computed tallies for history page
│       └── injuries.json             # latest scraped injury report
├── site_scripts/                     # the weekly update pipeline
│   ├── update_week.py                # the one entry point you run Tuesdays
│   ├── fetch_schedule.py             # next week's matchups + kickoff times
│   ├── fetch_odds.py                 # the-odds-api moneyline pull
│   ├── fetch_injuries.py             # nfl.com/injuries scraper
│   ├── predict.py                    # applies the logistic equation
│   ├── results.py                    # updates results.json with last week
│   ├── accuracy.py                   # recomputes accuracy.json
│   └── README.md                     # how to run it
└── docs/superpowers/specs/
    └── 2026-10-17-pocketpicks-design.md   # this document
```

GitHub Pages publishes from `/site` on the `main` branch after merge. The
branch is `pocketpicks-site` during development.

### Visual direction

Dark sportsbook base with modern breathing room:

- Background: near-black (`#0E1116`), card surface slightly lighter
  (`#1A1F26`).
- Accent: a single bright color used for the favored team's percentage,
  the "live" indicator and the week selector highlight. Suggested
  `#38E07B` (a confident green). CSS custom property so it can be
  swapped.
- Secondary accent for underdog / contrast: `#F0943B` (amber).
- Type: a bold display face for numbers (Inter 800 or similar), a quiet
  sans for body (Inter 400). Google Fonts.
- Numbers big and tabular: percentages, odds, scores all use tabular
  figures so they line up down a column.
- Lots of whitespace inside cards; cards themselves are dense with
  signal.

A logo file is produced before launch: a simple wordmark **PocketPicks**
with a tiny football icon tucked next to the "P" (the "pocket"). SVG,
two color variants (on-dark, on-light).

### Page: homepage (`index.html`)

Top of page:
- Logo and site name at the top-left.
- Nav: *This Week* (current), *History*, *About*.
- A banner strip: current NFL week, model season-to-date accuracy, and
  the model's record (e.g. "Week 7 • 2026 season • 42–18 (70%)").

Below the banner, a grid of **game cards**, one per matchup, sorted by
kickoff time (soonest first). Each card has:

- **Top-center:** kickoff date and time (visitor's local timezone,
  computed in JS).
- **Left:** away team logo, team name, season record.
- **Right:** home team logo, team name, season record.
- **Centerpiece:** the predicted winner's percentage as the biggest
  number on the card, with "home win" or "away win" label underneath.
  The percentage is colored with the accent for the favored team's side.
- **Visualization:** a horizontal bar split showing both teams'
  predicted win probability, color-coded, with the percentages labeled
  on each side.
- **Odds row:** bookmaker moneyline for each team, small text, labeled
  "Odds (consensus)".
- Clicking anywhere on the card opens the game detail page.

In Weeks 1–5, the percentage, bar and "favored" styling are replaced
with the plain text "Model warming up — needs 5 games of history per
team." Odds and kickoff time still appear.

### Page: game detail (`game.html?id=<game_id>`)

- Header with both teams, kickoff time, the prediction % and odds
  (same card content as the homepage, enlarged).
- **Team stat panels, side by side:**
  - Season record (e.g. 4-2)
  - Current streak (W3 or L1)
  - Last game: opponent, result, score
  - Last 5 games: a small inline list, each row with opponent, W/L,
    score, home/away marker
- **Injury report:** two columns, one per team, pulled from `injuries.json`.
  Each injury line shows player, position, status (Out, Doubtful,
  Questionable), and the reported injury. Timestamp of last fetch
  shown at the bottom of the panel.
- **Model inputs panel:** both teams' `last5_win_rate`, the computed
  differential, and the resulting probability, so the prediction is
  transparent.

### Page: history (`history.html`)

Two stacked sections.

The history page shows **the current 2026 season only** at launch.
Weeks fill in as the season progresses. Prior seasons (2022–2025) are
not displayed, so the user never sees in-sample inflated accuracy.

**Top: scoreboard with week selector.**
- A horizontal strip of week pills (Weeks 1 through the most recent
  completed week of the current season). Click a pill to focus that
  week.
- When a week is focused, show that week's game grid using the same
  card layout as the homepage, with results overlaid: a green ✓ on the
  correct pick, a red ✗ on the miss, and the final score. For
  Weeks 1–5, the week pill is shown but inert ("no model predictions").
- Below the grid, a one-line stat for the focused week: "Week 7:
  12–4 (75%)".

**Bottom: running tally.**
- A table or compact list of every week with per-week accuracy and
  cumulative accuracy to date.
- A sparkline chart at the top (Chart.js) of weekly accuracy with a
  horizontal reference line at the baseline "always home" rate (53.1%).
- Final row of the table: season overall accuracy and record.

At launch the page will have at most one or two weeks of real history
(mid-season 2026, model active from Week 6). The scoreboard shows a
small "model active from Week 6" note so a first-time visitor
understands why the earliest pills are inert.

Both views read from the same `results.json` and `accuracy.json` so the
numbers cannot disagree.

### Footer (every page)

- Email: `xyz@xyz.com` (placeholder, maintainer swaps before launch).
- One-line copyright: `© 2026 PocketPicks`.
- A quiet line: "Predictions from a trained logistic model
  (last-5 win rate differential). Not betting advice."

### Data model

Each `data/week_NN.json` has:

```json
{
  "season": 2026,
  "week": 7,
  "generated_at": "2026-10-14T10:12:00Z",
  "games": [
    {
      "id": "2026-W07-KC-DEN",
      "kickoff_utc": "2026-10-19T17:00:00Z",
      "home": {"team": "Kansas City Chiefs", "slug": "kc", "record": "5-1", "streak": "W3"},
      "away": {"team": "Denver Broncos", "slug": "den", "record": "3-3", "streak": "L1"},
      "prediction": {
        "home_win_prob": 0.78,
        "away_win_prob": 0.22,
        "favored": "home",
        "home_last5_win_rate": 0.80,
        "away_last5_win_rate": 0.40,
        "diff": 0.40,
        "model": "logistic_v1 (0.3271 + 1.8526 * diff)"
      },
      "odds": {
        "home_moneyline": -340,
        "away_moneyline": 270,
        "source": "the-odds-api consensus",
        "pulled_at": "2026-10-14T10:11:50Z"
      },
      "last5_home": [ ... five {opponent, result, score, home_away} entries ... ],
      "last5_away": [ ... ]
    }
  ]
}
```

`results.json` keyed by game id, storing final score and whether the
pick was correct, written when the update script runs the week after
each game. `accuracy.json` keyed by week, with `{correct, total,
pct, cumulative_correct, cumulative_total, cumulative_pct}`.

### The weekly update script

`python site_scripts/update_week.py --season 2026 --week 7`

The script owns the entire 2026-2027 data pipeline — it ingests
last week's completed games using the existing PFR crawler, regenerates
all per-game metrics using the existing plugin scripts, then produces
predictions for the upcoming week.

Behavior:
1. Confirm the current `season.json` and advance it if needed.
2. **Ingest last week's completed games into `dev_data/games/{season}_games.csv`**
   by invoking the existing `tools/nfl_crawler.py` for the previous
   week. New rows are appended; existing rows for that week are
   replaced.
3. **Regenerate the full set of per-season metrics** for the current
   season by invoking each plugin's `generate_season_*.py` script
   (`nfl-previous-five-win-rate`, `nfl-opponent-strength`,
   `nfl-previous-game-gap`, `nfl-travel-timezone`). These overwrite
   `dev_data/metrics/{season}_*.csv` with the latest data.
4. **Append last week's final scores and pick outcomes to `results.json`.**
   For each game predicted the week before, read the final score and
   record whether the pick was correct.
5. **Recompute `accuracy.json` from scratch from `results.json`.**
6. **Fetch the upcoming week's schedule** (opponents + kickoff times)
   from the nflverse schedules CSV. Filter to the target week and
   season.
7. For each upcoming game, compute each team's current
   `last5_win_rate` from `dev_data/metrics/{season}_win_rate.csv`,
   apply the logistic equation (`logit P = 0.3271 + 1.8526 × diff`),
   and attach the probabilities.
8. **Pull moneyline odds** for each upcoming game from the-odds-api
   (skipped silently with blank odds if no key).
9. **Fetch nfl.com injuries** respecting `robots.txt`; write
   `injuries.json` with per-team entries or an "unavailable" marker.
10. **Write the upcoming week's `data/week_NN.json`.**
11. Print a short summary of what was written and the git files that
    changed, so the maintainer can review and commit.

The script is idempotent for a given season+week; rerunning it
regenerates the files without duplicating entries. First-time setup for
a new season creates `dev_data/games/{season}_games.csv` and the
metric files from empty.

### Hosting

GitHub Pages, source `/site` folder on `main`. Custom domain decision
is deferred — the project ships on the default `github.io` URL and the
maintainer can add a `CNAME` later. 404 page falls back to the homepage.

### Browser support

Last two versions of Chrome, Safari, Firefox and Edge. Mobile Safari and
Chrome on Android. No IE. No JS framework polyfills needed.

### Accessibility

- Semantic HTML (nav, main, article, section).
- Color is never the only cue for the favored team: the percentage
  itself and a "FAVORED" badge both appear.
- Text contrast meets WCAG AA on the dark background.
- Nav and week pills are reachable by keyboard.

### Analytics / privacy

None at launch. No tracking scripts, no cookies.

### Launch plan

1. Scaffold `site/` with the three pages, placeholder data for one
   week, and the logo.
2. Build the update script end-to-end. For local verification only
   (not shown on the live site), run it against 2025 to confirm the
   pipeline produces the correct JSON shape and the generated
   percentages match the hold-out numbers in
   `project_log/2026_09_07.md`.
3. Run the update script against 2026 to seed `data/week_NN.json`
   files for weeks that have already been played in the current
   season, plus the upcoming week.
4. Verify all three pages render correctly on the real 2026 data.
5. Add the `.github/workflows/pages.yml` workflow, enable GitHub Pages,
   walk through the site on a phone.
6. Merge `pocketpicks-site` to `main`.
7. Maintainer runs the update script every Tuesday and pushes.

## What's left to the builder

The next step is a written implementation plan via
`superpowers:writing-plans`, which will break the above into ordered
work: logo and page scaffolding, data contract and placeholder files,
each update-script fetcher, the three pages' JavaScript, the history
scoreboard, and the launch pass. Specifics the plan will settle:

- Exact Chart.js version pin, viewport breakpoints, typography scale.
- Final choice of team logo source (SVG set, licensed for use).
- The-odds-api endpoint and request shape.
- CSS architecture (single stylesheet with sections, documented at the
  top).
- Error handling in the update script and whether unit tests cover the
  probability computation.
- The exact copy of the "model warming up" banner, the footer
  disclaimer and the About page.
