// Shared helpers for every PocketPicks page. ES module, no dependencies.

export const CONTACT_EMAIL = "xyz@xyz.com";
export const COPYRIGHT = "© 2026 PocketPicks";
export const DISCLAIMER =
  "Predictions from a trained logistic model (last-5 win rate differential). Not betting advice.";

const NAV_ITEMS = [
  { key: "home", label: "This Week", href: "index.html" },
  { key: "history", label: "History", href: "history.html" },
  { key: "about", label: "About", href: "about.html" },
];

/** Fetch a JSON file; throws if the response is not ok. */
export async function loadJSON(path) {
  const res = await fetch(path);
  if (!res.ok) {
    throw new Error(`Failed to load ${path}: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

/** ISO UTC timestamp -> kickoff string in the viewer's local time zone. */
export function formatKickoff(iso) {
  return new Date(iso).toLocaleString(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    timeZoneName: "short",
  });
}

/** Fraction -> whole percent string: 0.78 -> "78%". */
export function fmtPct(p) {
  return `${Math.round(p * 100)}%`;
}

/** American moneyline: -340 -> "-340", 270 -> "+270". */
export function fmtMoneyline(n) {
  return n > 0 ? `+${n}` : String(n);
}

/** Path to a team logo, relative to the site root. */
export function teamLogoPath(slug) {
  return `assets/img/teams/${slug}.svg`;
}

/** Tiny DOM builder: el("div", {className: "x", textContent: "y"}, [child, ...]). Never uses innerHTML. */
export function el(tag, props = {}, children = []) {
  const node = document.createElement(tag);
  Object.assign(node, props);
  for (const child of children) node.append(child);
  return node;
}

/** Team logo <img>; if the SVG is missing, swap in a text badge with the uppercased slug. */
export function teamLogo(slug) {
  const img = document.createElement("img");
  img.className = "team-logo";
  img.alt = "";
  img.width = 48;
  img.height = 48;
  img.addEventListener(
    "error",
    () => img.replaceWith(el("span", { className: "team-badge", textContent: slug.toUpperCase() })),
    { once: true },
  );
  img.src = teamLogoPath(slug);
  return img;
}

/** Inject the shared site header + nav into `target`. `active` is "home" | "history" | "about". */
export function renderNav(target, active) {
  const logo = el("a", { className: "site-logo", href: "index.html" }, [
    el("img", { src: "assets/img/logo.svg", alt: "PocketPicks", width: 230, height: 48 }),
  ]);
  const nav = el("nav", { className: "site-nav" });
  nav.setAttribute("aria-label", "Main");
  for (const item of NAV_ITEMS) {
    const a = el("a", { href: item.href, textContent: item.label });
    if (item.key === active) a.setAttribute("aria-current", "page");
    nav.append(a);
  }
  target.className = "site-header";
  target.replaceChildren(el("div", { className: "container" }, [logo, nav]));
}

/** Inject the shared footer (email, copyright, disclaimer) into `target`. */
export function renderFooter(target) {
  const mail = el("a", { href: `mailto:${CONTACT_EMAIL}`, textContent: CONTACT_EMAIL });
  target.className = "site-footer";
  target.replaceChildren(
    el("div", { className: "container" }, [
      el("p", {}, ["Contact: ", mail]),
      el("p", { textContent: COPYRIGHT }),
      el("p", { className: "disclaimer", textContent: DISCLAIMER }),
    ]),
  );
}
