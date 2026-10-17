// Game detail page: ?id=2026-W07-kc-den -> header, team stat panels, model inputs, injuries.
import { loadJSON, fmtPct, formatKickoff, teamLogo, el } from "./common.js";
import { renderGameCard } from "./home.js";

const INJURY_REPORT_URL = "https://www.nfl.com/injuries/";
const INJURY_LINK_TEXT = "View current injury report at nfl.com/injuries →";

/** "2026-W07-kc-den" -> "data/week_07.json"; null if the id has no week token. */
function weekFileForId(id) {
  const m = /W(\d+)/.exec(id || "");
  if (!m) return null;
  return `data/week_${m[1].padStart(2, "0")}.json`;
}

function notFound() {
  return el("div", { className: "empty-state" }, [
    el("h1", { textContent: "Game not found" }),
    el("p", { textContent: "We couldn't find that game." }),
    el("a", { href: "index.html", textContent: "← Back to this week's picks" }),
  ]);
}

function statRow(label, value) {
  return el("div", { className: "stat-row" }, [
    el("dt", { textContent: label }),
    el("dd", { className: "tabular", textContent: value }),
  ]);
}

function resultLine(r) {
  const where = r.home_away === "home" ? "vs" : "@";
  return `${r.result} ${r.score} ${where} ${String(r.opponent).toUpperCase()}`;
}

function last5Item(r) {
  const cls = r.result === "W" ? "win" : r.result === "L" ? "loss" : "tie";
  return el("li", { className: "last5-item" }, [
    el("span", {
      className: `result-chip ${cls}`,
      textContent: r.result,
      title: r.result === "W" ? "Win" : r.result === "L" ? "Loss" : "Tie",
    }),
    el("span", { className: "last5-score tabular", textContent: r.score }),
    el("span", {
      className: "last5-opp",
      textContent: `${r.home_away === "home" ? "vs" : "@"} ${String(r.opponent).toUpperCase()}`,
    }),
  ]);
}

function teamPanel(team, side, last5) {
  const stats = [statRow("Record", team.record), statRow("Streak", team.streak)];
  stats.push(statRow("Last game", last5.length ? resultLine(last5[0]) : "—"));

  const list = last5.length
    ? el("ol", { className: "last5-list" }, last5.map(last5Item))
    : el("p", { className: "text-muted", textContent: "No games played yet." });

  return el("section", { className: "card team-panel" }, [
    el("div", { className: "team-panel-head" }, [
      teamLogo(team.slug),
      el("div", {}, [
        el("h2", { textContent: team.team }),
        el("div", {
          className: "text-muted panel-sub",
          textContent: side === "home" ? "Home" : "Away",
        }),
      ]),
    ]),
    el("dl", { className: "stat-list" }, stats),
    el("h3", { className: "panel-subhead", textContent: `Last ${last5.length || 5} games` }),
    list,
  ]);
}

function modelInputsPanel(game) {
  const p = game.prediction;
  const favSide = p.favored;
  const favProb = favSide === "home" ? p.home_win_prob : p.away_win_prob;
  const signed = (n) => `${n > 0 ? "+" : ""}${n.toFixed(2)}`;
  return el("section", { className: "card model-panel" }, [
    el("h2", { textContent: "Model inputs" }),
    el("dl", { className: "stat-list" }, [
      statRow(`${game.home.team} last-5 win rate`, fmtPct(p.home_last5_win_rate)),
      statRow(`${game.away.team} last-5 win rate`, fmtPct(p.away_last5_win_rate)),
      statRow("Differential (home − away)", signed(p.diff)),
      statRow(`${game[favSide].team} win probability`, fmtPct(favProb)),
    ]),
    el("p", { className: "text-muted model-note", textContent: p.model }),
  ]);
}

function injuryColumn(team, entries) {
  const body = entries.length
    ? el(
        "ul",
        { className: "injury-list" },
        entries.map((e) =>
          el("li", { className: "injury-item" }, [
            el("span", { className: "injury-player", textContent: `${e.player} (${e.position})` }),
            el("span", { className: "injury-detail" }, [
              el("span", {
                className: `status-badge status-${String(e.status).toLowerCase().replace(/\s+/g, "-")}`,
                textContent: e.status,
              }),
              ` ${e.injury ?? ""}`,
            ]),
          ]),
        ),
      )
    : el("p", { className: "text-muted", textContent: "No reported injuries." });
  return el("div", { className: "injury-col" }, [
    el("h3", { textContent: team.team }),
    body,
  ]);
}

function injuriesSection(game, injuries) {
  const head = el("h2", { textContent: "Injuries" });
  if (!injuries || injuries.available !== true) {
    return el("section", { className: "card injuries" }, [
      head,
      el("p", {}, [
        el("a", {
          href: INJURY_REPORT_URL,
          target: "_blank",
          rel: "noopener noreferrer",
          textContent: INJURY_LINK_TEXT,
        }),
      ]),
    ]);
  }
  const teams = injuries.teams || {};
  const cols = el("div", { className: "injury-cols" }, [
    injuryColumn(game.away, teams[game.away.slug] || []),
    injuryColumn(game.home, teams[game.home.slug] || []),
  ]);
  const fetched = injuries.pulled_at ? `Last fetched: ${formatKickoff(injuries.pulled_at)}` : "";
  return el("section", { className: "card injuries" }, [
    head,
    cols,
    el("p", { className: "text-muted injuries-fetched", textContent: fetched }),
  ]);
}

async function findGame(id) {
  const file = weekFileForId(id);
  if (!file) return null;
  try {
    const week = await loadJSON(file);
    return (week.games || []).find((g) => g.id === id) || null;
  } catch (err) {
    console.warn(err);
    return null;
  }
}

async function main(root) {
  const id = new URLSearchParams(window.location.search).get("id");
  const game = id ? await findGame(id) : null;
  if (!game) {
    document.title = "Game not found | PocketPicks";
    root.replaceChildren(notFound());
    return;
  }

  let injuries = null;
  try {
    injuries = await loadJSON("data/injuries.json");
  } catch (err) {
    console.warn(err);
  }

  document.title = `${game.away.team} @ ${game.home.team} | PocketPicks`;

  const header = renderGameCard(game, { linkToDetail: false });
  header.classList.add("game-header");

  const sections = [
    el("p", {}, [el("a", { href: "index.html", textContent: "← All games" })]),
    header,
    el("div", { className: "panel-grid" }, [
      teamPanel(game.away, "away", game.last5_away || []),
      teamPanel(game.home, "home", game.last5_home || []),
    ]),
  ];
  if (game.prediction) sections.push(modelInputsPanel(game));
  sections.push(injuriesSection(game, injuries));

  root.replaceChildren(...sections);
}

const root = document.getElementById("game-root");
if (root) {
  main(root).catch((err) => {
    console.error(err);
    root.replaceChildren(notFound());
  });
}
