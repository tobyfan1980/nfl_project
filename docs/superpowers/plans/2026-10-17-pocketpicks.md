# PocketPicks Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a public, static NFL prediction website (PocketPicks) plus a one-command Python update script that writes the site's data files, so pushing to GitHub publishes the latest week's picks on GitHub Pages.

**Architecture:** A vanilla HTML/CSS/JS site in `site/` reads JSON data files from `site/data/` at page load. A Python pipeline in `site_scripts/` ingests completed games (reusing the existing PFR crawler and metric plugins), applies the repo's trained logistic model, fetches odds and injuries, and writes those JSON files directly into `site/data/`. The data files are the only coupling between the pipeline and the site: the maintainer runs the script, commits the changed JSON, and pushes; a GitHub Actions workflow publishes `site/` to Pages.

**Tech Stack:** HTML5, CSS (custom properties, no framework), vanilla ES modules, Chart.js (pinned, from cdnjs) for the accuracy sparkline. Python 3 (stdlib + `requests`, `beautifulsoup4`, `pandas` — already in `requirements.txt`) for the pipeline. GitHub Actions for Pages deploy.

**Spec:** `docs/superpowers/specs/2026-10-17-pocketpicks-design.md`

## Global Constraints

- Static only: no backend, no build step, no server-side rendering. Pages render from committed HTML/CSS/JS + JSON.
- No third-party dependencies except Chart.js (cdnjs, pinned to an exact version ≥ 2 weeks old, e.g. `chart.js@4.4.1`) and Google Fonts (Inter).
- Predictor is fixed: `logit P(home_win) = 0.3271 + 1.8526 × (home_last5_win_rate − away_last5_win_rate)`; `P = 1 / (1 + exp(-logit))`. Hard-code these two coefficients. No retraining.
- Weeks 1–5 have no prediction (last-5 win rate needs 5 prior games). Those weeks show the schedule with a "model warming up" note, no percentage.
- History page shows the **current 2026 season only**. Never publish 2022–2025 to the live site.
- The script writes JSON into `site/data/`; committing + pushing those files is what updates the live site. The script must never require editing any file by hand.
- Respect `robots.txt` on every scrape. If `nfl.com/injuries/` is disallowed or fails, write `{"available": false, ...}` and the UI links out instead of embedding.
- `the-odds-api` key read from `~/.pocketpicks_odds_key`; if absent, odds fields are blank/omitted and the UI hides the odds row. No key is ever committed.
- Colors as CSS custom properties: bg `#0E1116`, surface `#1A1F26`, favored/green `#38E07B`, underdog/amber `#F0943B`. WCAG AA contrast. Color is never the only favored cue — a "FAVORED" badge + the percentage also carry it.
- Footer on every page: email `xyz@xyz.com`, `© 2026 PocketPicks`, and "Predictions from a trained logistic model (last-5 win rate differential). Not betting advice."
- Mobile: no horizontal scroll at 375px; 16px side gutters.
- Attribution on every commit:
  `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`

## Review Focus

- **Missing or future week data** — a visitor loads `index.html` when `site/data/season.json` points at a week whose `week_NN.json` isn't written yet (off-week, or before the first run). Expected: a clear "no picks posted yet" state, not a crashed/blank page. → Task 3.
- **Weeks 1–5 games (no prediction field)** — cards and the detail page receive a game with no `prediction` object. Expected: schedule + "model warming up" copy, no percentage, no broken layout. → Tasks 3, 4.
- **Injuries unavailable** — `injuries.json` is `{"available": false}`. Expected: detail page shows the outbound nfl.com link, not an empty panel or error. → Task 5.
- **Odds absent** — a game's `odds` is missing (no API key at generation time). Expected: the odds row is hidden on both the card and detail page; nothing else shifts. → Tasks 4, 5.
- **History tally consistency** — the cumulative numbers in `accuracy.json` must equal the sum of per-week results in `results.json`. Expected: history page totals match the per-week pills exactly. → Tasks 6, 10.
- **Mobile width** — all three pages at 375px. Expected: no horizontal scroll, cards stack. → Task 2.

---

## Task 1: Site scaffold, shared assets, and data contract

**Files:**
- Create: `site/assets/css/styles.css`
- Create: `site/assets/js/common.js`
- Create: `site/assets/img/logo.svg`, `site/assets/img/favicon.svg`
- Create: `site/assets/vendor/chart.min.js` (Chart.js 4.4.1, downloaded from cdnjs, committed)
- Create: `site/data/season.json`, `site/data/week_07.json`, `site/data/results.json`, `site/data/accuracy.json`, `site/data/injuries.json` (hand-written fixtures used for front-end development and as the documented contract)
- Create: `site/data/README.md` (documents each file's shape — this is the data contract)
- Create: `docs/superpowers/plans/.gitkeep` is not needed; ignore.
- Test: `site_scripts/tests/test_data_contract.py`

**Interfaces:**
- Produces: the JSON shapes every other task reads/writes. Canonical shapes (match the spec's "Data model"):
  - `season.json`: `{"season": 2026, "current_week": 7, "model_active_from_week": 6}`
  - `week_NN.json`: `{"season", "week", "generated_at", "games": [Game, ...]}` where `Game` = `{"id", "kickoff_utc", "home": Team, "away": Team, "prediction": Prediction|null, "odds": Odds|null, "last5_home": [Result×≤5], "last5_away": [...]}`; `Team` = `{"team", "slug", "record", "streak"}`; `Prediction` = `{"home_win_prob", "away_win_prob", "favored": "home"|"away", "home_last5_win_rate", "away_last5_win_rate", "diff", "model"}`; `Odds` = `{"home_moneyline", "away_moneyline", "books": int, "source", "pulled_at"}`; `Result` = `{"opponent", "result": "W"|"L"|"T", "score": "27-20", "home_away": "home"|"away"}`.
  - `results.json`: `{"<game_id>": {"season", "week", "final": "27-20", "winner": "home"|"away", "picked": "home"|"away"|null, "correct": bool|null}}`
  - `accuracy.json`: `{"season": 2026, "weeks": [{"week", "correct", "total", "pct", "cumulative_correct", "cumulative_total", "cumulative_pct"}], "overall": {"correct", "total", "pct", "record": "42-18"}}`
  - `injuries.json`: `{"available": bool, "pulled_at", "reason"?, "teams": {"<slug>": [{"player", "position", "status", "injury"}]}}`

- [ ] **Step 1: Write `site/data/README.md`** documenting every file shape above verbatim; this is the authoritative contract other tasks cite.

- [ ] **Step 2: Hand-write fixture JSON** for `season.json`, one `week_07.json` with 3 games (one favored-home with prediction+odds, one favored-away, one Weeks-1–5-style game with `prediction: null` and `odds: null`), `results.json` (weeks 6–7), `accuracy.json` matching those results, and `injuries.json` with `available: true` and two teams. The fixtures must be internally consistent (accuracy totals equal the results sums).

- [ ] **Step 3: Write the failing test** `test_fixtures_match_contract` in `site_scripts/tests/test_data_contract.py`: load each fixture, assert required keys/types per the contract, and assert `accuracy.json.overall.correct` equals the count of `correct: true` entries in `results.json`.

- [ ] **Step 4: Run test to verify it fails**
Run: `python3 -m pytest site_scripts/tests/test_data_contract.py -v`
Expected: FAIL (fixtures or assertions not yet aligned) — fix fixtures until the shape is right, but keep the test if already green after careful authoring; the point is the contract is pinned.

- [ ] **Step 5: Write `styles.css`** — `:root` custom properties for the colors above, Inter via Google Fonts `@import`, a dark `body` background, card/surface styles, tabular-figures utility (`font-variant-numeric: tabular-nums`), responsive grid (cards stack under 640px, 16px gutters), nav, footer, week-pill, and a `.favored-badge`. Document sections at the top of the file.

- [ ] **Step 6: Write `logo.svg` and `favicon.svg`** — a simple "PocketPicks" wordmark with a small football icon; SVG, legible on the dark background.

- [ ] **Step 7: Download Chart.js 4.4.1** from cdnjs into `site/assets/vendor/chart.min.js`.

- [ ] **Step 8: Write `common.js`** (ES module) exporting: `loadJSON(path)` (fetch + json, throws on non-ok), `formatKickoff(iso)` (to viewer local time), `fmtPct(p)` (e.g. `0.78 → "78%"`), `fmtMoneyline(n)` (`-340`, `+270`), `teamLogoPath(slug)`, and `renderFooter(el)` / `renderNav(el, active)` helpers that inject the shared footer/nav so copy lives in one place.

- [ ] **Step 9: Commit**
```bash
git add site/ site_scripts/tests/test_data_contract.py
git commit -m "feat(pocketpicks): site scaffold, shared assets, data contract + fixtures"
```

## Task 2: Page shells + base layout verification

**Files:**
- Create: `site/index.html`, `site/game.html`, `site/history.html`, `site/about.html`
- Create: `site/404.html`
- Modify: `site/assets/css/styles.css` (layout refinements found while viewing)

**Interfaces:**
- Consumes: `common.js` `renderNav`/`renderFooter`, `styles.css`.
- Produces: four pages with shared `<head>` (viewport meta, favicon, fonts, styles), a `<nav>` mount, a `<main>` with a page-specific root element (`#picks-root`, `#game-root`, `#history-root`), and a `<footer>` mount. Each page loads its own module (`home.js`/`game.js`/`history.js`) with `<script type="module">`.

- [ ] **Step 1: Write the four HTML shells + 404.html**, each wiring nav, main root, footer mounts, and (for index/game/history) its module script tag. `about.html` holds static copy (what the model is, the disclaimer, the team). `404.html` redirects to `index.html`.

- [ ] **Step 2: Verify in a browser** — open `site/index.html` via the preview server; confirm nav + footer render from `common.js`, fonts load, dark theme applies, no console errors.

- [ ] **Step 3: Verify mobile width** — resize to 375px; confirm no horizontal scroll and the nav/footer wrap cleanly. (Covers Review Focus: mobile width.)

- [ ] **Step 4: Commit**
```bash
git add site/
git commit -m "feat(pocketpicks): page shells, 404, base layout"
```

## Task 3: Homepage — this week's picks

**Files:**
- Create: `site/assets/js/home.js`
- Modify: `site/assets/css/styles.css` (card styles)
- Test: manual browser verification against fixtures

**Interfaces:**
- Consumes: `common.js`, `season.json`, `week_NN.json`.
- Produces: renders into `#picks-root`. A reusable `renderGameCard(game, {linkToDetail: true})` function also used (imported) by `history.js`.

- [ ] **Step 1: Write `home.js`** — load `season.json`, then `week_{current_week}.json`. Render a banner ("Week N • 2026 season • {overall record+pct from accuracy.json}") and a grid of cards sorted by `kickoff_utc`. Each card: kickoff time top-center, away (left)/home (right) logos+name+record, centerpiece predicted-winner percentage with "home/away win" label colored by favored side, a horizontal split probability bar, a FAVORED badge, and an odds row (`fmtMoneyline`, label "Consensus (median of N books)"). Whole card links to `game.html?id=<id>`.

- [ ] **Step 2: Handle the no-prediction case** — when `game.prediction` is null, replace the percentage/bar/badge with "Model warming up — needs 5 games of history per team."; still show kickoff and (if present) odds. (Covers Review Focus: Weeks 1–5.)

- [ ] **Step 3: Handle missing/absent odds** — when `game.odds` is null, omit the odds row entirely with no layout gap. (Covers Review Focus: odds absent.)

- [ ] **Step 4: Handle missing week file** — if `week_{current_week}.json` fetch fails, render a friendly "No picks posted yet — check back Tuesday." state instead of throwing. (Covers Review Focus: missing/future week data.)

- [ ] **Step 5: Verify in browser against fixtures** — confirm the three fixture games render correctly (favored-home, favored-away, warming-up), the bar widths match the percentages, and the card links carry the right `id`. Resize to 375px and confirm cards stack.

- [ ] **Step 6: Commit**
```bash
git add site/
git commit -m "feat(pocketpicks): homepage pick cards"
```

## Task 4: Game detail page

**Files:**
- Create: `site/assets/js/game.js`
- Modify: `site/assets/css/styles.css` (detail layout)

**Interfaces:**
- Consumes: `common.js`, `renderGameCard` from `home.js`, `week_NN.json`, `injuries.json`.
- Produces: renders into `#game-root` using `?id=` query param.

- [ ] **Step 1: Write `game.js`** — parse `id` from the query string, derive the week from the id (`2026-W07-...`), load that `week_NN.json`, find the game. Render an enlarged header (reuse card content), two side-by-side team stat panels (record, streak, last game, last-5 list from `last5_home`/`last5_away` with W/L + score + home/away marker), and a "Model inputs" panel (both `last5_win_rate`, `diff`, resulting probability) — the inputs panel is omitted when `prediction` is null.

- [ ] **Step 2: Render injuries** — read `injuries.json`; when `available: true`, two columns keyed by team slug with player/position/status/injury and a "last fetched" timestamp. When `available: false`, render the outbound link "View current injury report at nfl.com/injuries →". (Covers Review Focus: injuries unavailable.)

- [ ] **Step 3: Handle not-found id** — unknown/missing `id` renders "Game not found" with a link home, no throw.

- [ ] **Step 4: Verify in browser** — click through from the homepage fixture to each game; confirm stats, last-5, model inputs, injuries (both available and the `available:false` branch — temporarily flip the fixture), and the odds-absent branch. Check 375px.

- [ ] **Step 5: Commit**
```bash
git add site/
git commit -m "feat(pocketpicks): game detail page"
```

## Task 5: History page — scoreboard + accuracy

**Files:**
- Create: `site/assets/js/history.js`
- Modify: `site/assets/css/styles.css` (pills, table, chart container)

**Interfaces:**
- Consumes: `common.js`, `renderGameCard` from `home.js`, Chart.js vendor, `season.json`, `results.json`, `accuracy.json`, played `week_NN.json` files.
- Produces: renders into `#history-root`.

- [ ] **Step 1: Write `history.js`** — a week-pill strip (Weeks 1..current completed week). Clicking a pill loads that `week_NN.json`, renders its games via `renderGameCard` with results overlaid (✓/✗ + final score from `results.json`), and shows the week's one-line stat from `accuracy.json`. Weeks 1–5 pills are inert with a "model active from Week 6" note.

- [ ] **Step 2: Render the running tally** — a table of every week's per-week and cumulative accuracy from `accuracy.json`, a final overall row, and a Chart.js line sparkline of weekly `pct` with a reference line at 53.1% (baseline "always home").

- [ ] **Step 3: Handle sparse/early season** — at launch only weeks 6–7 have data; earlier/future pills render inert or absent without error.

- [ ] **Step 4: Verify in browser against fixtures** — confirm pills, overlaid ✓/✗, the per-week stat, the table totals equal the sum of per-week results, and the chart renders. Check 375px.

- [ ] **Step 5: Commit**
```bash
git add site/
git commit -m "feat(pocketpicks): history scoreboard and accuracy chart"
```

## Task 6: Predictor module

**Files:**
- Create: `site_scripts/predict.py`
- Test: `site_scripts/tests/test_predict.py`

**Interfaces:**
- Produces: `predict_home_win(home_last5: float, away_last5: float) -> dict` returning `{"home_win_prob", "away_win_prob", "favored", "diff", "model": "logistic_v1 (0.3271 + 1.8526 * diff)"}`, probabilities rounded to 4 dp; and `win_prob(diff: float) -> float` (the raw logistic).

- [ ] **Step 1: Write the failing test** `test_win_prob` asserting `win_prob(0.0)` ≈ `1/(1+exp(-0.3271))` ≈ `0.5811` and that the 0.5 decision boundary is at `diff ≈ -0.1766` (from the spec's logistic); and `test_predict_home_win_favored` asserting a positive diff yields `favored == "home"` and probs summing to 1.

```python
def test_win_prob():
    assert abs(win_prob(0.0) - 0.5811) < 1e-3
    assert win_prob(-0.1766) == pytest.approx(0.5, abs=1e-3)
```

- [ ] **Step 2: Run test to verify it fails**
Run: `python3 -m pytest site_scripts/tests/test_predict.py -v`
Expected: FAIL with import/define error.

- [ ] **Step 3: Implement `predict.py`** with the hard-coded coefficients `B0=0.3271`, `B1=1.8526` and `win_prob`/`predict_home_win` as specified.

- [ ] **Step 4: Run test to verify it passes**
Run: `python3 -m pytest site_scripts/tests/test_predict.py -v`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add site_scripts/predict.py site_scripts/tests/test_predict.py
git commit -m "feat(pocketpicks): logistic predictor module"
```

## Task 7: Schedule fetcher (nflverse)

**Files:**
- Create: `site_scripts/fetch_schedule.py`
- Test: `site_scripts/tests/test_fetch_schedule.py` (uses a saved CSV sample, no network)

**Interfaces:**
- Produces: `parse_schedule(csv_text: str, season: int, week: int) -> list[dict]` → `[{"id", "kickoff_utc", "home_team", "home_slug", "away_team", "away_slug"}]`; and `fetch_schedule(season, week) -> list[dict]` (downloads the nflverse `games.csv` raw URL, then `parse_schedule`). A `TEAM_SLUGS` mapping (full name → slug) lives here and is the single source of truth for slugs, imported by the pipeline.

- [ ] **Step 1: Save a small nflverse `games.csv` sample** (a handful of 2024 rows incl. game_id, season, week, gameday, gametime, home_team, away_team) into `site_scripts/tests/fixtures/nflverse_sample.csv`.

- [ ] **Step 2: Write the failing test** `test_parse_schedule` asserting it returns the right matchups for a (season, week), builds `id` as `{season}-W{week:02d}-{away_slug}-{home_slug}`, and converts gameday+gametime (US Eastern) to a UTC ISO `kickoff_utc`.

- [ ] **Step 3: Run test to verify it fails**
Run: `python3 -m pytest site_scripts/tests/test_fetch_schedule.py -v`
Expected: FAIL.

- [ ] **Step 4: Implement `fetch_schedule.py`** — `parse_schedule` over the sample columns, `TEAM_SLUGS`, and `fetch_schedule` using `requests` against the nflverse raw CSV URL. Note: nflverse team codes may need mapping to the full team names used in `dev_data` — include that mapping in `TEAM_SLUGS`/a `NFLVERSE_TO_FULL` dict.

- [ ] **Step 5: Run test to verify it passes**
Run: `python3 -m pytest site_scripts/tests/test_fetch_schedule.py -v`
Expected: PASS

- [ ] **Step 6: Commit**
```bash
git add site_scripts/fetch_schedule.py site_scripts/tests/
git commit -m "feat(pocketpicks): nflverse schedule fetcher"
```

## Task 8: Odds fetcher (the-odds-api)

**Files:**
- Create: `site_scripts/fetch_odds.py`
- Test: `site_scripts/tests/test_fetch_odds.py` (saved JSON sample, no network)

**Interfaces:**
- Produces: `aggregate_odds(api_response: list, home_team: str, away_team: str) -> dict|None` → `{"home_moneyline", "away_moneyline", "books", "source": "the-odds-api", "pulled_at"}` using the **median** moneyline across US books for each side; and `fetch_odds(games: list) -> dict[game_id, Odds]` that reads the key from `~/.pocketpicks_odds_key`, returns `{}` (logging a notice) when the key is absent, and matches API events to our games by team name.

- [ ] **Step 1: Save a sample the-odds-api response** (one event, 3 bookmakers, h2h market) into `site_scripts/tests/fixtures/odds_sample.json`.

- [ ] **Step 2: Write the failing tests** `test_aggregate_odds_median` (median across the 3 books, `books == 3`) and `test_fetch_odds_no_key` (monkeypatch the home path to a missing file → returns `{}`, does not raise). (Covers Review Focus: odds absent at the source.)

- [ ] **Step 3: Run tests to verify they fail**
Run: `python3 -m pytest site_scripts/tests/test_fetch_odds.py -v`
Expected: FAIL.

- [ ] **Step 4: Implement `fetch_odds.py`** per the interface; median via `statistics.median`, team-name matching tolerant of the API's naming.

- [ ] **Step 5: Run tests to verify they pass**
Run: `python3 -m pytest site_scripts/tests/test_fetch_odds.py -v`
Expected: PASS

- [ ] **Step 6: Commit**
```bash
git add site_scripts/fetch_odds.py site_scripts/tests/
git commit -m "feat(pocketpicks): odds fetcher with median aggregation"
```

## Task 9: Injury fetcher (nfl.com, robots-aware)

**Files:**
- Create: `site_scripts/fetch_injuries.py`
- Test: `site_scripts/tests/test_fetch_injuries.py` (saved HTML sample, no network)

**Interfaces:**
- Produces: `parse_injuries(html: str, slug_for: callable) -> dict` → `{"<slug>": [{"player","position","status","injury"}]}`; and `fetch_injuries() -> dict` returning the full `injuries.json` body (`{"available", "pulled_at", "reason"?, "teams"}`). `fetch_injuries` first checks `nfl.com/robots.txt` with `urllib.robotparser`; if disallowed or the request fails, returns `{"available": false, "reason": ...}` and does not fetch the page.

- [ ] **Step 1: Save a trimmed `nfl.com/injuries` HTML sample** into `site_scripts/tests/fixtures/injuries_sample.html`.

- [ ] **Step 2: Write the failing tests** `test_parse_injuries` (extracts players grouped by team slug) and `test_fetch_injuries_blocked` (monkeypatch robots check to disallow → `{"available": false}`, no network call). (Covers Review Focus: injuries unavailable.)

- [ ] **Step 3: Run tests to verify they fail**
Run: `python3 -m pytest site_scripts/tests/test_fetch_injuries.py -v`
Expected: FAIL.

- [ ] **Step 4: Implement `fetch_injuries.py`** — robots check, respectful single request with the project's user-agent, BeautifulSoup parse, graceful `available:false` on any failure.

- [ ] **Step 5: Run tests to verify they pass**
Run: `python3 -m pytest site_scripts/tests/test_fetch_injuries.py -v`
Expected: PASS

- [ ] **Step 6: Commit**
```bash
git add site_scripts/fetch_injuries.py site_scripts/tests/
git commit -m "feat(pocketpicks): robots-aware injury fetcher"
```

## Task 10: Results + accuracy modules

**Files:**
- Create: `site_scripts/results.py`
- Create: `site_scripts/accuracy.py`
- Test: `site_scripts/tests/test_results.py`, `site_scripts/tests/test_accuracy.py`

**Interfaces:**
- Consumes: `dev_data/games/{season}_games.csv` (completed games, home/away via `@` marker), prior `week_NN.json` (to know what was picked).
- Produces:
  - `results.py`: `update_results(results: dict, season, week, games_csv_path, week_json_path) -> dict` — for each game in that week's `week_json`, read the final score from the games CSV, set `winner`, `picked` (from the stored prediction, or null for warming-up weeks), and `correct`.
  - `accuracy.py`: `compute_accuracy(results: dict, season) -> dict` — produce the `accuracy.json` body (per-week + cumulative + overall record), counting only games with a non-null `picked`.

- [ ] **Step 1: Write the failing test** `test_compute_accuracy_totals` — given a `results` dict with known correct/total per week, assert per-week `pct`, `cumulative_pct`, and that `overall.correct` equals the sum of per-week `correct` and `overall.total` the sum of per-week totals (this is the tally-consistency guarantee). (Covers Review Focus: history tally consistency.)

- [ ] **Step 2: Write the failing test** `test_update_results_marks_correct` — a small games CSV + a week_json with one home-favored pick where home won → `correct: true`; one where the pick lost → `correct: false`; one warming-up game (`picked: null`) → `correct: null` and excluded from accuracy.

- [ ] **Step 3: Run tests to verify they fail**
Run: `python3 -m pytest site_scripts/tests/test_results.py site_scripts/tests/test_accuracy.py -v`
Expected: FAIL.

- [ ] **Step 4: Implement `results.py` and `accuracy.py`** per the interfaces.

- [ ] **Step 5: Run tests to verify they pass**
Expected: PASS

- [ ] **Step 6: Commit**
```bash
git add site_scripts/results.py site_scripts/accuracy.py site_scripts/tests/
git commit -m "feat(pocketpicks): results tracking and accuracy computation"
```

## Task 11: Data-pipeline wrappers (crawler + metric regeneration)

**Files:**
- Create: `site_scripts/pipeline.py`
- Test: `site_scripts/tests/test_pipeline.py` (subprocess calls mocked/monkeypatched)

**Interfaces:**
- Produces:
  - `ingest_week(season: int, week: int) -> None` — invoke `tools/nfl_crawler.py --year {season} --week {week}` and merge its output into `dev_data/games/{season}_games.csv` (append new rows, replace existing rows for that week).
  - `regenerate_metrics(season: int) -> None` — invoke each plugin generator (`nfl-previous-five-win-rate`, `nfl-opponent-strength`, `nfl-previous-game-gap`, `nfl-travel-timezone`) for the season with `--overwrite`, writing `dev_data/metrics/{season}_*.csv`.
  - `current_last5(season: int, team_full: str, before_date: str) -> float|None` — read `dev_data/metrics/{season}_win_rate.csv` for the team's most recent row before the target week; `None` if the team has < 5 prior games (→ warming-up).

- [ ] **Step 1: Write the failing test** `test_current_last5_reads_metric` against a tiny `{season}_win_rate.csv` fixture: returns the latest `win_rate` for a team before a date, and `None` when absent.

- [ ] **Step 2: Write the failing test** `test_ingest_and_regenerate_invoke_scripts` — monkeypatch `subprocess.run` and assert `ingest_week`/`regenerate_metrics` call the expected scripts with the expected args (no real network/crawl).

- [ ] **Step 3: Run tests to verify they fail**
Expected: FAIL.

- [ ] **Step 4: Implement `pipeline.py`** — resolve script paths relative to the repo root; use `subprocess.run([...], check=True)`; the CSV merge for `ingest_week` dedupes on (week, teams, date).

- [ ] **Step 5: Run tests to verify they pass**
Expected: PASS

- [ ] **Step 6: Commit**
```bash
git add site_scripts/pipeline.py site_scripts/tests/
git commit -m "feat(pocketpicks): pipeline wrappers for crawler and metrics"
```

## Task 12: `update_week.py` orchestration (predict + write site data)

**Files:**
- Create: `site_scripts/update_week.py`
- Create: `site_scripts/README.md`
- Test: `site_scripts/tests/test_update_week.py` (all fetchers/pipeline monkeypatched; asserts files written into a temp `site/data`)

**Interfaces:**
- Consumes: every module above.
- Produces: the CLI `python site_scripts/update_week.py --season 2026 --week 7 [--skip-ingest] [--data-dir site/data]`. Writes/overwrites `site/data/week_{week:02d}.json`, updates `site/data/results.json`, `site/data/accuracy.json`, `site/data/season.json` (`current_week = week`), and `site/data/injuries.json`. Prints a summary listing the changed files and reminds the maintainer to `git add site/data && git commit && git push`.

- [ ] **Step 1: Write the failing test** `test_update_week_writes_site_data` — monkeypatch `ingest_week`, `regenerate_metrics`, `fetch_schedule`, `fetch_odds`, `fetch_injuries`, and `current_last5` to return fixtures; run `main(["--season","2026","--week","7","--data-dir",tmp,"--skip-ingest"])`; assert `week_07.json` exists with a prediction built from the predictor, `season.json.current_week == 7`, and `accuracy.json` totals are self-consistent.

- [ ] **Step 2: Run test to verify it fails**
Run: `python3 -m pytest site_scripts/tests/test_update_week.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `update_week.py`** following the spec's 11-step behavior, in order: season.json → ingest (unless `--skip-ingest`) → regenerate metrics → update results → compute accuracy → fetch schedule → predict per game (warming-up → `prediction: null` when `current_last5` is `None`) → fetch odds → fetch injuries → write all `site/data/*.json` → print summary. Idempotent per (season, week).

- [ ] **Step 4: Run test to verify it passes**
Expected: PASS

- [ ] **Step 5: Write `site_scripts/README.md`** — how to install deps, set the odds key, run `update_week.py` each Tuesday, and the `git add site/data && git commit && git push` step that publishes. State plainly: the script does the prediction and writes the page data; pushing is what updates the live GitHub Pages site.

- [ ] **Step 6: Run the full Python test suite**
Run: `python3 -m pytest site_scripts/tests/ -v`
Expected: all PASS

- [ ] **Step 7: Commit**
```bash
git add site_scripts/
git commit -m "feat(pocketpicks): update_week orchestration writes site data"
```

## Task 13: Real 2026 data seed + end-to-end verification

**Files:**
- Modify: `site/data/*.json` (replaced by real generated output)

**Interfaces:**
- Consumes: the whole pipeline against live sources.

- [ ] **Step 1: Run the pipeline for real** for the current 2026 season — ingest completed weeks (6 onward), regenerate metrics, and run `update_week.py` for each played week plus the upcoming week, so `site/data/` holds real `week_NN.json`, `results.json`, `accuracy.json`, `injuries.json`. If live network/data for 2026 isn't yet available in this environment, generate from the latest available season instead and note it; the maintainer reruns for 2026 at launch.

- [ ] **Step 2: Spot-check the generated numbers** — pick one game and confirm the probability equals `predict.win_prob(home_last5 − away_last5)`; confirm `accuracy.json` overall matches the per-week sums.

- [ ] **Step 3: Verify all three pages in a browser** against the real data — homepage picks, a detail page, history scoreboard + chart. Check console for errors and 375px layout.

- [ ] **Step 4: Commit**
```bash
git add site/data/
git commit -m "chore(pocketpicks): seed site data from pipeline"
```

## Task 14: GitHub Pages deploy workflow

**Files:**
- Create: `.github/workflows/pages.yml`

**Interfaces:**
- Produces: a workflow that, on push to `main`, uploads `site/` as the Pages artifact and deploys it (actions/upload-pages-artifact + actions/deploy-pages, with `pages: write` / `id-token: write` permissions).

- [ ] **Step 1: Write `.github/workflows/pages.yml`** — trigger on push to `main`, single deploy job, `upload-pages-artifact` with `path: site`, `deploy-pages`. Pin action versions.

- [ ] **Step 2: Validate the workflow YAML** (syntax) locally.

- [ ] **Step 3: Document enabling Pages** in `site_scripts/README.md` — repo Settings → Pages → Source: GitHub Actions (one-time).

- [ ] **Step 4: Commit**
```bash
git add .github/workflows/pages.yml site_scripts/README.md
git commit -m "ci(pocketpicks): GitHub Pages deploy workflow"
```
