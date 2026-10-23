// History page: week-by-week scoreboard (picks vs. results) and the running accuracy tally.
// Everything is derived from the same season.json / results.json / accuracy.json fetch, so the
// per-week stat line, the tally table and the chart cannot disagree.
import { loadJSON, fmtPct, el } from "./common.js";
import { renderGameCard } from "./home.js";

export const BASELINE_PCT = 53.1; // "always pick the home team" baseline, in percent
const CHART_SRC = "assets/vendor/chart.min.js";

const weekFile = (week) => `data/week_${String(week).padStart(2, "0")}.json`;

function emptyState(text) {
  return el("p", { className: "empty-state", textContent: text });
}

/** "3-1" style record for a week entry from accuracy.json. */
const weekRecord = (w) => `${w.correct}-${w.total - w.correct}`;

/* ---------- Scoreboard ---------- */

/** "KC 27, DEN 20"-style line from a results.json entry; final is "<home>-<away>". */
function finalScoreText(result, home, away) {
  const [h, a] = String(result.final).split("-");
  return `Final: ${away.toUpperCase()} ${a} @ ${home.toUpperCase()} ${h}`;
}

function resultFooter(result, home, away) {
  const items = [];
  if (result.correct === true) {
    items.push(
      el("span", { className: "result-badge hit", textContent: "✓ Correct" }),
    );
  } else if (result.correct === false) {
    items.push(
      el("span", { className: "result-badge miss", textContent: "✗ Missed" }),
    );
  } else {
    items.push(el("span", { className: "result-badge none", textContent: "No pick" }));
  }
  items.push(
    el("span", { className: "final-score tabular", textContent: finalScoreText(result, home, away) }),
  );
  return el("div", { className: "result-footer" }, items);
}

/** Wrap renderGameCard and append the outcome marker; the card itself is not reimplemented. */
function renderResultCard(game, result) {
  const card = renderGameCard(game, { linkToDetail: true });
  if (!result) return card;
  if (result.correct === true) card.classList.add("result-hit");
  else if (result.correct === false) card.classList.add("result-miss");
  card.append(resultFooter(result, game.home.slug, game.away.slug));
  return card;
}

/** Fallback when week_NN.json is not published: a compact card built from results.json alone. */
function renderResultOnlyCard(id, result) {
  // id = {season}-W{NN}-{home}-{away}
  const parts = id.split("-");
  const away = parts.pop();
  const home = parts.pop();
  const card = el("div", { className: "card game-card" }, [
    el("div", { className: "teams-line", textContent: `${away.toUpperCase()} @ ${home.toUpperCase()}` }),
  ]);
  if (result.correct === true) card.classList.add("result-hit");
  else if (result.correct === false) card.classList.add("result-miss");
  card.append(resultFooter(result, home, away));
  return card;
}

function weekStat(accWeek, week) {
  if (!accWeek || !accWeek.total) {
    return `Week ${week}: no graded picks yet`;
  }
  return `Week ${week}: ${weekRecord(accWeek)} (${fmtPct(accWeek.pct)})`;
}

function buildScoreboard(ctx) {
  const { season, accByWeek, resultsByWeek, maxWeek, firstWeek } = ctx;

  const hasData = (w) => accByWeek.has(w) || resultsByWeek.has(w);

  const pillList = el("ul", { className: "week-pills" });
  pillList.setAttribute("aria-label", "Select a week");
  const pills = new Map();
  for (let w = firstWeek; w <= maxWeek; w++) {
    const btn = el("button", { type: "button", className: "week-pill tabular", textContent: `Week ${w}` });
    if (hasData(w)) {
      btn.setAttribute("aria-pressed", "false");
      btn.addEventListener("click", () => select(w));
    } else {
      btn.disabled = true;
      btn.classList.add("inert");
      btn.title = "No data for this week";
    }
    pills.set(w, btn);
    pillList.append(el("li", {}, [btn]));
  }

  const stat = el("p", { className: "week-stat tabular" });
  stat.setAttribute("aria-live", "polite");
  const grid = el("div", { className: "card-grid" });
  const status = el("div", {});

  let token = 0;
  async function select(week) {
    const mine = ++token;
    for (const [w, btn] of pills) {
      if (btn.disabled) continue;
      btn.setAttribute("aria-pressed", String(w === week));
    }
    stat.textContent = weekStat(accByWeek.get(week), week);
    status.replaceChildren();

    let weekData = null;
    try {
      weekData = await loadJSON(weekFile(week));
    } catch (err) {
      console.warn(err);
    }
    if (mine !== token) return; // a newer click superseded this one

    const games =
      weekData && Array.isArray(weekData.games) && weekData.season === season ? weekData.games : null;
    if (games && games.length) {
      const sorted = [...games].sort(
        (a, b) => new Date(a.kickoff_utc) - new Date(b.kickoff_utc) || a.id.localeCompare(b.id),
      );
      grid.replaceChildren(...sorted.map((g) => renderResultCard(g, resultsByWeek.get(week)?.get(g.id))));
      return;
    }

    // No published week file: fall back to whatever results.json knows for the week.
    const results = resultsByWeek.get(week);
    if (results && results.size) {
      status.replaceChildren(
        el("p", {
          className: "text-muted",
          textContent: `Full game cards for Week ${week} aren't published; showing results only.`,
        }),
      );
      grid.replaceChildren(...[...results].map(([id, r]) => renderResultOnlyCard(id, r)));
    } else {
      grid.replaceChildren();
      status.replaceChildren(emptyState(`No games found for Week ${week}.`));
    }
  }

  const section = el("section", { className: "history-section" }, [
    el("h2", { textContent: "Scoreboard" }),
    pillList,
    stat,
    status,
    grid,
  ]);

  // Default to the most recent week that has data.
  let initial = null;
  for (let w = maxWeek; w >= firstWeek; w--) {
    if (hasData(w)) {
      initial = w;
      break;
    }
  }
  if (initial !== null) select(initial);
  else status.replaceChildren(emptyState("No completed weeks with predictions yet."));

  return section;
}

/* ---------- Running tally ---------- */

function td(text, className) {
  return el("td", { textContent: text, className: className || "" });
}

function buildTally(accuracy) {
  const rows = accuracy.weeks.map((w) =>
    el("tr", {}, [
      el("th", { scope: "row", textContent: `Week ${w.week}` }),
      td(weekRecord(w), "tabular"),
      td(w.total ? fmtPct(w.pct) : "—", "tabular"),
      td(`${w.cumulative_correct}-${w.cumulative_total - w.cumulative_correct}`, "tabular"),
      td(w.cumulative_total ? fmtPct(w.cumulative_pct) : "—", "tabular"),
    ]),
  );

  const o = accuracy.overall;
  const head = el("thead", {}, [
    el("tr", {}, ["Week", "Record", "Acc.", "Season", "Season %"].map((t) =>
      el("th", { scope: "col", textContent: t }),
    )),
  ]);
  const foot = el("tfoot", {}, [
    el("tr", {}, [
      el("th", { scope: "row", textContent: "Overall" }),
      td(o.record, "tabular"),
      td(o.total ? fmtPct(o.pct) : "—", "tabular"),
      td(o.record, "tabular"),
      td(o.total ? fmtPct(o.pct) : "—", "tabular"),
    ]),
  ]);

  const table = el("table", { className: "tally-table" }, [head, el("tbody", {}, rows), foot]);
  table.append(el("caption", { className: "visually-hidden", textContent: "Weekly and cumulative pick accuracy" }));
  return el("div", { className: "table-wrap" }, [table]);
}

function loadChartJS() {
  if (window.Chart) return Promise.resolve(window.Chart);
  return new Promise((resolve, reject) => {
    const s = document.createElement("script");
    s.src = CHART_SRC;
    s.onload = () => (window.Chart ? resolve(window.Chart) : reject(new Error("Chart.js did not initialise")));
    s.onerror = () => reject(new Error(`Failed to load ${CHART_SRC}`));
    document.head.append(s);
  });
}

async function drawChart(canvas, fallbackEl, accuracy) {
  let Chart;
  try {
    Chart = await loadChartJS();
  } catch (err) {
    console.error(err);
    canvas.hidden = true;
    fallbackEl.hidden = false;
    return;
  }
  const css = getComputedStyle(document.documentElement);
  const color = (name) => css.getPropertyValue(name).trim();
  const weeks = accuracy.weeks.filter((w) => w.total > 0);
  const labels = weeks.map((w) => `Wk ${w.week}`);

  new Chart(canvas, {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: "Weekly accuracy",
          data: weeks.map((w) => Math.round(w.pct * 1000) / 10),
          borderColor: color("--favored"),
          backgroundColor: color("--favored"),
          pointRadius: 4,
          pointHoverRadius: 6,
          tension: 0.25,
          order: 1,
        },
        {
          label: `Always-home baseline (${BASELINE_PCT}%)`,
          data: weeks.map(() => BASELINE_PCT),
          borderColor: color("--underdog"),
          borderDash: [6, 4],
          borderWidth: 2,
          pointRadius: 0,
          pointHoverRadius: 0,
          order: 2,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      scales: {
        y: {
          min: 0,
          max: 100,
          ticks: { color: color("--muted"), callback: (v) => `${v}%` },
          grid: { color: color("--border") },
        },
        x: { ticks: { color: color("--muted") }, grid: { color: color("--border") } },
      },
      plugins: {
        legend: { labels: { color: color("--text"), boxWidth: 24 } },
        tooltip: { callbacks: { label: (c) => `${c.dataset.label}: ${c.parsed.y}%` } },
      },
    },
  });
}

function buildTallySection(accuracy) {
  const section = el("section", { className: "history-section" }, [
    el("h2", { textContent: "Running tally" }),
  ]);
  if (!accuracy.weeks.length) {
    section.append(emptyState("No graded games yet."));
    return section;
  }
  const o = accuracy.overall;
  section.append(
    el("p", {
      className: "tally-summary tabular",
      textContent: `Season so far: ${o.record} (${o.total ? fmtPct(o.pct) : "—"})`,
    }),
  );

  const canvas = el("canvas", {});
  canvas.setAttribute("role", "img");
  canvas.setAttribute(
    "aria-label",
    `Weekly accuracy by week compared with the ${BASELINE_PCT}% always-home baseline. See the table for the numbers.`,
  );
  const fallback = el("p", { className: "text-muted", hidden: true, textContent: "Chart unavailable; see the table." });
  const chartBox = el("div", { className: "chart-box" }, [canvas]);
  section.append(chartBox, fallback, buildTally(accuracy));
  drawChart(canvas, fallback, accuracy);
  return section;
}

/* ---------- Entry ---------- */

async function main(root) {
  let season;
  try {
    season = await loadJSON("data/season.json");
  } catch (err) {
    console.error(err);
    root.replaceChildren(emptyState("History is unavailable right now."));
    return;
  }

  const [resRes, accRes] = await Promise.allSettled([
    loadJSON("data/results.json"),
    loadJSON("data/accuracy.json"),
  ]);
  const results = resRes.status === "fulfilled" ? resRes.value : {};
  const accuracyRaw = accRes.status === "fulfilled" ? accRes.value : null;
  if (resRes.status === "rejected") console.warn(resRes.reason);
  if (accRes.status === "rejected") console.warn(accRes.reason);

  // Current season only: drop anything stamped with another season.
  const accuracy =
    accuracyRaw && accuracyRaw.season === season.season && Array.isArray(accuracyRaw.weeks)
      ? accuracyRaw
      : { season: season.season, weeks: [], overall: { correct: 0, total: 0, pct: 0, record: "0-0" } };

  const resultsByWeek = new Map();
  for (const [id, r] of Object.entries(results)) {
    if (r.season !== season.season) continue;
    if (!resultsByWeek.has(r.week)) resultsByWeek.set(r.week, new Map());
    resultsByWeek.get(r.week).set(id, r);
  }
  const accByWeek = new Map(accuracy.weeks.map((w) => [w.week, w]));

  // Weeks before the model is active have no picks and are hidden entirely:
  // pills run from model_active_from_week to the latest week with data.
  const firstWeek = Math.max(1, Number(season.model_active_from_week) || 1);
  const maxWeek = Math.max(0, ...[...resultsByWeek.keys(), ...accByWeek.keys()].filter((w) => w >= firstWeek));

  if (maxWeek === 0) {
    root.replaceChildren(el("h1", { textContent: "History" }), emptyState("No completed weeks yet — check back after this week's games."));
    return;
  }

  root.replaceChildren(
    el("h1", { textContent: "History" }),
    buildScoreboard({ season: season.season, accByWeek, resultsByWeek, maxWeek, firstWeek }),
    buildTallySection(accuracy),
  );
}

// Only auto-run on the history page.
const root = document.getElementById("history-root");
if (root) {
  main(root).catch((err) => {
    console.error(err);
    root.replaceChildren(el("h1", { textContent: "History" }), emptyState("History is unavailable right now."));
  });
}
