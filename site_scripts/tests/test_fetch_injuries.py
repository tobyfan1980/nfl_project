"""Tests for the injury fetcher (site_scripts/fetch_injuries.py).

Offline only: parse_injuries runs against a saved trimmed nfl.com/injuries
sample (tests/fixtures/injuries_sample.html). fetch_injuries is exercised with
the network stubbed out; the real page fetch is never unit-tested. Import path
comes from conftest.py.
"""
from pathlib import Path

import pytest
import requests

import fetch_injuries
from fetch_injuries import parse_injuries, slug_for_team

HTML = (Path(__file__).parent / "fixtures" / "injuries_sample.html").read_text()


def test_parse_injuries():
    teams = parse_injuries(HTML, slug_for_team)
    assert set(teams) == {"sea", "den"}
    assert teams["sea"] == [
        {"player": "Zach Charbonnet", "position": "RB", "status": "Out", "injury": "Knee"},
        {"player": "Chazz Surratt", "position": "LB", "status": "Out", "injury": "Calf"},
    ]
    assert teams["den"] == [
        {"player": "Talanoa Hufanga", "position": "S", "status": "Out", "injury": "Ankle"},
        {"player": "Riley Moss", "position": "CB", "status": "Questionable", "injury": "Ribs"},
        {"player": "Pat Surtain II", "position": "CB", "status": "Doubtful", "injury": "Ankle"},
    ]


def test_parse_injuries_skips_unknown_team_and_empty_html():
    assert parse_injuries(HTML, lambda label: None) == {}
    assert parse_injuries("<html></html>", slug_for_team) == {}


def test_slug_for_team_accepts_nickname_and_full_name():
    assert slug_for_team("Seahawks") == "sea"
    assert slug_for_team("Seattle Seahawks") == "sea"
    assert slug_for_team("49ers") == "sf"
    assert slug_for_team("Washington Commanders") == "wsh"
    assert slug_for_team("Not A Team") is None


def _no_page_fetch(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("page must not be fetched: " + repr(a))

    monkeypatch.setattr(fetch_injuries.requests, "get", boom)


def test_fetch_injuries_blocked(monkeypatch):
    monkeypatch.setattr(fetch_injuries, "_robots_allows", lambda url: False)
    _no_page_fetch(monkeypatch)
    out = fetch_injuries.fetch_injuries()
    assert out["available"] is False
    assert out["teams"] == {}
    assert "robots" in out["reason"]
    assert out["pulled_at"].endswith("Z")


def test_robots_disallow_rule_blocks_fetch(monkeypatch):
    """Real _robots_allows against a robots.txt body that disallows /injuries/."""
    class Resp:
        status_code = 200
        text = "User-agent: *\nDisallow: /injuries/\n"

    calls = []

    def fake_get(url, **kw):
        calls.append(url)
        assert url.endswith("/robots.txt"), "only robots.txt may be fetched"
        return Resp()

    monkeypatch.setattr(fetch_injuries.requests, "get", fake_get)
    out = fetch_injuries.fetch_injuries()
    assert out["available"] is False and out["teams"] == {}
    assert calls == ["https://www.nfl.com/robots.txt"]


def test_fetch_injuries_robots_unreachable(monkeypatch):
    def fail(url, **kw):
        raise requests.ConnectionError("down")

    monkeypatch.setattr(fetch_injuries.requests, "get", fail)
    out = fetch_injuries.fetch_injuries()
    assert out["available"] is False and out["teams"] == {}
    assert "robots" in out["reason"]


def test_fetch_injuries_page_request_fails(monkeypatch):
    monkeypatch.setattr(fetch_injuries, "_robots_allows", lambda url: True)

    def fail(url, **kw):
        raise requests.Timeout("slow")

    monkeypatch.setattr(fetch_injuries.requests, "get", fail)
    out = fetch_injuries.fetch_injuries()
    assert out["available"] is False and out["teams"] == {}
    assert out["reason"]


def test_fetch_injuries_allowed(monkeypatch):
    """robots allows -> single page GET with the project UA -> parsed teams."""
    order = []

    class Resp:
        def __init__(self, text, status=200):
            self.text, self.status_code = text, status

        def raise_for_status(self):
            pass

    def fake_get(url, **kw):
        order.append(url)
        assert kw["headers"]["User-Agent"] == fetch_injuries.USER_AGENT
        if url.endswith("/robots.txt"):
            return Resp("User-agent: *\nDisallow: /account/\n")
        return Resp(HTML)

    monkeypatch.setattr(fetch_injuries.requests, "get", fake_get)
    out = fetch_injuries.fetch_injuries()
    assert order == ["https://www.nfl.com/robots.txt", "https://www.nfl.com/injuries/"]
    assert out["available"] is True
    assert "reason" not in out
    assert set(out["teams"]) == {"sea", "den"}
    assert out["pulled_at"].endswith("Z")


def test_fetch_injuries_page_without_table_is_unavailable(monkeypatch):
    """A JS-only shell with no injury tables must not be reported as 'available'."""
    monkeypatch.setattr(fetch_injuries, "_robots_allows", lambda url: True)

    class Resp:
        status_code = 200
        text = "<html><body><div id='app'></div></body></html>"

        def raise_for_status(self):
            pass

    monkeypatch.setattr(fetch_injuries.requests, "get", lambda url, **kw: Resp())
    out = fetch_injuries.fetch_injuries()
    assert out["available"] is False and out["teams"] == {}
