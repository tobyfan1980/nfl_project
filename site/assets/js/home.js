// Homepage: this week's picks. Also exports renderGameCard for reuse (history, game pages).
import {
  loadJSON,
  formatKickoff,
  fmtPct,
  fmtMoneyline,
  teamLogo,
  el,
} from "./common.js";

export const WARMING_UP_TEXT = "Model warming up — needs 5 games of history per team.";
export const NO_PICKS_TEXT = "No picks posted yet — check back Tuesday.";

const weekFile = (week) => `data/week_${String(week).padStart(2, "0")}.json`;

function teamBlock(team, side, isFavored) {
  const children = [
    teamLogo(team.slug),
    el("span", { className: "team-name", textContent: team.team }),
    el("span", { className: "team-record tabular", textContent: team.record }),
  ];
  if (isFavored) children.push(el("span", { className: "favored-badge", textContent: "Favored" }));
  return el("div", { className: `team team-${side}` }, children);
}

function predictionSection(game) {
  const p = game.prediction;
  const favSide = p.favored; // "home" | "away"
  const favTeam = game[favSide].team;
  const favProb = favSide === "home" ? p.home_win_prob : p.away_win_prob;
  const favPct = Math.round(favProb * 100);
  const awayPct = favSide === "away" ? favPct : 100 - favPct;
  const homePct = 100 - awayPct;
  const cls = (side) => (side === favSide ? "favored" : "underdog");

  const pct = el("div", { className: "pick" }, [
    el("div", { className: "card-pct favored tabular", textContent: fmtPct(favProb) }),
    el("div", {
      className: "pick-label",
      textContent: `${favSide === "home" ? "Home" : "Away"} win`,
    }),
  ]);

  const bar = el("div", { className: "prob-bar" }, [
    el("span", { className: cls("away") }),
    el("span", { className: cls("home") }),
  ]);
  bar.children[0].style.width = `${awayPct}%`;
  bar.children[1].style.width = `${homePct}%`;
  bar.setAttribute("role", "img");
  bar.setAttribute(
    "aria-label",
    `${game.away.team} ${awayPct}%, ${game.home.team} ${homePct}%. ${favTeam} favored.`,
  );

  const legend = el("div", { className: "prob-legend tabular" }, [
    el("span", { textContent: `${game.away.slug.toUpperCase()} ${awayPct}%` }),
    el("span", { textContent: `${game.home.slug.toUpperCase()} ${homePct}%` }),
  ]);

  return [pct, bar, legend];
}

function oddsRow(game) {
  const o = game.odds;
  return el("div", { className: "odds-row" }, [
    el("div", {
      className: "odds-label",
      textContent: `Consensus (median of ${o.books} books)`,
    }),
    el("div", { className: "odds-lines tabular" }, [
      el("span", {
        textContent: `${game.away.slug.toUpperCase()} ${fmtMoneyline(o.away_moneyline)}`,
      }),
      el("span", {
        textContent: `${game.home.slug.toUpperCase()} ${fmtMoneyline(o.home_moneyline)}`,
      }),
    ]),
  ]);
}

/**
 * Build one game card.
 * @param {object} game  A Game from week_NN.json (see site/data/README.md).
 * @param {{linkToDetail?: boolean}} [opts]  linkToDetail (default true): render the whole card as
 *   a link to game.html?id=<id>. When false it is a plain <div class="card"> (e.g. on the detail page).
 * @returns {HTMLElement}
 */
export function renderGameCard(game, { linkToDetail = true } = {}) {
  const p = game.prediction;
  const card = linkToDetail
    ? el("a", {
        className: "card game-card",
        href: `game.html?id=${encodeURIComponent(game.id)}`,
      })
    : el("div", { className: "card game-card" });

  card.append(el("div", { className: "card-meta", textContent: formatKickoff(game.kickoff_utc) }));

  card.append(
    el("div", { className: "teams" }, [
      teamBlock(game.away, "away", !!p && p.favored === "away"),
      el("span", { className: "teams-at", textContent: "@" }),
      teamBlock(game.home, "home", !!p && p.favored === "home"),
    ]),
  );

  if (p) {
    card.append(...predictionSection(game));
  } else {
    card.append(el("p", { className: "warming-up", textContent: WARMING_UP_TEXT }));
  }

  if (game.odds) card.append(oddsRow(game));

  return card;
}

function renderBanner(season, week, accuracy) {
  const parts = [
    el("strong", { textContent: `Week ${week}` }),
    el("span", { textContent: `${season} season` }),
  ];
  const o = accuracy && accuracy.overall;
  if (o && o.total > 0) {
    parts.push(
      el("span", { className: "tabular", textContent: `Overall: ${o.record} (${fmtPct(o.pct)})` }),
    );
  }
  return el("div", { className: "banner" }, parts);
}

function emptyState(text) {
  return el("p", { className: "empty-state", textContent: text });
}

async function main(root) {
  let season;
  try {
    season = await loadJSON("data/season.json");
  } catch (err) {
    console.error(err);
    root.replaceChildren(emptyState(NO_PICKS_TEXT));
    return;
  }

  const [weekResult, accResult] = await Promise.allSettled([
    loadJSON(weekFile(season.current_week)),
    loadJSON("data/accuracy.json"),
  ]);
  const accuracy = accResult.status === "fulfilled" ? accResult.value : null;
  const banner = renderBanner(season.season, season.current_week, accuracy);

  if (weekResult.status === "rejected" || !Array.isArray(weekResult.value.games) || !weekResult.value.games.length) {
    if (weekResult.status === "rejected") console.warn(weekResult.reason);
    root.replaceChildren(banner, emptyState(NO_PICKS_TEXT));
    return;
  }

  const games = [...weekResult.value.games].sort(
    (a, b) => new Date(a.kickoff_utc) - new Date(b.kickoff_utc) || a.id.localeCompare(b.id),
  );
  const grid = el("div", { className: "card-grid" }, games.map((g) => renderGameCard(g)));
  root.replaceChildren(banner, grid);
}

// Only auto-run on the homepage; other pages import renderGameCard without side effects.
const root = document.getElementById("picks-root");
if (root) main(root);
