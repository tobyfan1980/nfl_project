"""PocketPicks injury fetcher: per-team injury report from nfl.com/injuries.

robots.txt is ALWAYS honoured. ``fetch_injuries`` first reads
https://www.nfl.com/robots.txt; if the injuries path is disallowed, or robots.txt
cannot be read, or the page request fails for any reason, it returns
``{"available": false, "reason": ..., "teams": {}, "pulled_at": ...}`` and the
site links out to nfl.com instead. It never works around a disallow.

When nfl.com gives no report, ``fetch_injury_report`` falls back to the
nflverse injuries release (the league's official report as a CSV on GitHub,
refreshed daily during the season).

Output shape matches site/data/README.md ``injuries.json``. Only players with a
game status of Out / Doubtful / Questionable are reported (players merely on the
practice report with no game designation are skipped).
"""
from __future__ import annotations

import csv
import io
import logging
import re
from datetime import datetime, timezone
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

from fetch_schedule import TEAM_SLUGS

log = logging.getLogger(__name__)

INJURIES_URL = "https://www.nfl.com/injuries/"
ROBOTS_URL = "https://www.nfl.com/robots.txt"
# Same respectful UA as tools/nfl_crawler.py.
USER_AGENT = "Mozilla/5.0 (compatible; NFLStatsCrawler/1.0; +https://github.com/user/nfl-crawler)"
# Bare product token for robots.txt group matching. RobotFileParser matches the
# text before "/" of the agent string, so passing the full UA would match only
# "mozilla" and silently ignore a `User-agent: NFLStatsCrawler` group.
ROBOTS_AGENT = "NFLStatsCrawler"
TIMEOUT = 20
NFLVERSE_INJURIES_URL = (
    "https://github.com/nflverse/nflverse-data/releases/download/injuries/injuries_{season}.csv"
)
# nflverse team abbreviations that differ from our slugs.
NFLVERSE_SLUGS = {"LA": "lar", "WAS": "wsh"}
STATUSES = ("Out", "Doubtful", "Questionable")

# normalized full name / nickname -> slug ("seattleseahawks" and "seahawks" -> "sea").
_ALIASES: dict = {}
for _full, _slug in TEAM_SLUGS.items():
    _ALIASES[re.sub(r"[^a-z0-9]", "", _full.lower())] = _slug
    _ALIASES[re.sub(r"[^a-z0-9]", "", _full.split()[-1].lower())] = _slug


def slug_for_team(label: str):
    """Map an nfl.com team label (nickname or full name) to our slug, else None."""
    return _ALIASES.get(re.sub(r"[^a-z0-9]", "", (label or "").lower()))


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _unavailable(reason: str) -> dict:
    return {"available": False, "pulled_at": _now(), "reason": reason, "teams": {}}


def _robots_allows(url: str) -> bool:
    """True only if robots.txt was read and permits our UA to fetch ``url``.

    Mirrors RobotFileParser.read() semantics (401/403 -> disallow all, other 4xx
    -> allow all) but with a timeout; a 5xx or network error raises, which the
    caller treats as "unavailable" (conservative: no robots verdict, no fetch).
    """
    resp = requests.get(ROBOTS_URL, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
    status = resp.status_code
    if status in (401, 403):
        return False
    if 400 <= status < 500:
        return True
    if status != 200:
        raise RuntimeError(f"robots.txt returned HTTP {status}")
    rp = RobotFileParser()
    rp.parse(resp.text.splitlines())
    return rp.can_fetch(ROBOTS_AGENT, url)


def parse_injuries(html: str, slug_for) -> dict:
    """Parse nfl.com/injuries HTML into ``{slug: [{player, position, status, injury}]}``.

    Each game is a ``section.nfl-o-injury-report__unit`` holding one table per
    team, headed by a ``.d3-o-section-sub-title`` team label. Tables whose label
    ``slug_for`` cannot resolve are skipped.
    """
    soup = BeautifulSoup(html, "html.parser")
    teams: dict = {}
    for table in soup.select("section.nfl-o-injury-report__unit table"):
        label_el = table.find_previous(class_="d3-o-section-sub-title")
        slug = slug_for(label_el.get_text(" ", strip=True)) if label_el else None
        if not slug:
            continue
        for tr in table.select("tbody tr"):
            cells = [td.get_text(" ", strip=True) for td in tr.find_all("td")]
            if len(cells) < 5 or cells[4] not in STATUSES:
                continue
            player, position, injury, _practice, status = cells[:5]
            teams.setdefault(slug, []).append(
                {"player": player, "position": position, "status": status, "injury": injury}
            )
    return teams


def fetch_injuries() -> dict:
    """Return the full injuries.json body; ``available`` is False on any obstacle."""
    path = urlsplit(INJURIES_URL).path
    try:
        allowed = _robots_allows(INJURIES_URL)
    except Exception as exc:  # no robots verdict -> do not fetch
        log.warning("injuries: could not read robots.txt: %s", exc)
        return _unavailable("could not read robots.txt")
    if not allowed:
        log.info("injuries: robots.txt disallows %s; linking out instead", path)
        return _unavailable("robots.txt disallows fetch")

    try:
        # Do not follow redirects: a target URL would not have been checked
        # against robots.txt, so a 3xx is treated as unavailable.
        resp = requests.get(
            INJURIES_URL,
            headers={"User-Agent": USER_AGENT},
            timeout=TIMEOUT,
            allow_redirects=False,
        )
        if 300 <= resp.status_code < 400:
            log.warning("injuries: page redirected (HTTP %s); not following", resp.status_code)
            return _unavailable("page redirected; not followed (robots.txt not checked for target)")
        resp.raise_for_status()
        teams = parse_injuries(resp.text, slug_for_team)
    except Exception as exc:
        log.warning("injuries: fetch/parse failed: %s", exc)
        return _unavailable(f"request failed: {type(exc).__name__}")
    if not teams:
        # JS-only shell or changed markup: never present an empty report as real.
        return _unavailable("no injury data found in page")
    return {"available": True, "pulled_at": _now(), "teams": teams}


def download_nflverse_injuries(season: int) -> str:
    """Download the nflverse injuries CSV text (monkeypatched in tests)."""
    url = NFLVERSE_INJURIES_URL.format(season=season)
    resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=60)
    resp.raise_for_status()
    return resp.text


def parse_nflverse_injuries(csv_text: str, season: int, week: int) -> dict:
    """Official game statuses for one week from the nflverse injuries CSV.

    Players with no Out / Doubtful / Questionable designation (practice report
    only) are skipped, matching the nfl.com parser.
    """
    teams: dict = {}
    for row in csv.DictReader(io.StringIO(csv_text)):
        if row.get("season") != str(season) or row.get("week") != str(week):
            continue
        if row.get("game_type", "REG") != "REG":
            continue
        status = (row.get("report_status") or "").strip()
        if status not in STATUSES:
            continue
        abbr = (row.get("team") or "").strip()
        slug = NFLVERSE_SLUGS.get(abbr, abbr.lower())
        if not re.fullmatch(r"[a-z]+", slug):
            continue
        injury = (row.get("report_primary_injury") or row.get("practice_primary_injury") or "").strip()
        teams.setdefault(slug, []).append({
            "player": (row.get("full_name") or "").strip() or "Unknown",
            "position": (row.get("position") or "").strip() or "-",
            "status": status,
            "injury": injury or "Not listed",
        })
    return teams


def fetch_injury_report(season: int, week: int) -> dict:
    """nfl.com first; if that gives no report, the nflverse injuries CSV."""
    primary = fetch_injuries()
    if primary["available"]:
        return primary
    try:
        teams = parse_nflverse_injuries(download_nflverse_injuries(season), season, week)
    except Exception as exc:
        log.warning("injuries: nflverse fallback failed: %s", exc)
        return primary
    if len(teams) < 2:
        log.warning("injuries: nflverse has no week %s game statuses yet", week)
        return primary
    log.info("injuries: nfl.com unavailable (%s); using nflverse week %s report (%d teams)",
             primary.get("reason"), week, len(teams))
    return {"available": True, "pulled_at": _now(), "teams": teams}
