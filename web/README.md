# Predictions website

`docs/index.html` is a single self-contained page (no build step, no JS
dependencies) showing upcoming-week home win probabilities and the season
accuracy record.

## Regenerate

```bash
python tools/build_site.py --year 2025 --upcoming-week 18
```

`--upcoming-week N` shows week N as upcoming predictions with scores hidden,
and drops later weeks. Weeks 6 through N-1 feed the accuracy section. Omit the
flag to render every available week as completed results.

The script reads `dev_data/metrics/{year}_all_game_metrics.csv` and scores each
game with the working logistic model from `project_log/2026_09_07.md`:

```
logit P(home win) = 0.3271 + 1.8526 * (home_last5_win_rate - away_last5_win_rate)
```

Page markup lives in `web/template.html`; the script injects the season data
into its `/*__SITE_DATA__*/null` placeholder. Edit the template, not
`docs/index.html`, which is generated output.

## Hosting

GitHub Pages serves this with no extra infrastructure: in repository Settings ->
Pages, set Source to "Deploy from a branch", branch `main`, folder `/docs`. The
site is then at `https://tobyfan1980.github.io/nfl_project/`. Publishing a new
week means regenerating the page and pushing the commit.
