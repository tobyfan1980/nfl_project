"""Tests for the injuries-only refresh (site_scripts/update_injuries.py)."""
import json

import update_injuries


def test_refreshes_only_injuries_for_current_week(tmp_path, monkeypatch):
    (tmp_path / "season.json").write_text(json.dumps({"season": 2026, "current_week": 11}))
    (tmp_path / "week_11.json").write_text('{"keep": true}')
    calls = []

    def fake_report(season, week):
        calls.append((season, week))
        return {"available": True, "pulled_at": "2026-11-19T06:00:00Z",
                "teams": {"kc": [{"player": "A", "position": "WR",
                                  "status": "Out", "injury": "Knee"}]}}

    monkeypatch.setattr(update_injuries, "fetch_injury_report", fake_report)
    assert update_injuries.main(["--data-dir", str(tmp_path)]) == 0
    assert calls == [(2026, 11)]
    assert json.loads((tmp_path / "injuries.json").read_text())["teams"]["kc"][0]["player"] == "A"
    assert (tmp_path / "week_11.json").read_text() == '{"keep": true}'
    assert sorted(p.name for p in tmp_path.iterdir()) == ["injuries.json", "season.json", "week_11.json"]


def test_missing_season_json_fails(tmp_path):
    assert update_injuries.main(["--data-dir", str(tmp_path)]) == 1


def test_same_report_leaves_file_untouched(tmp_path, monkeypatch):
    (tmp_path / "season.json").write_text(json.dumps({"season": 2026, "current_week": 11}))
    report = {"available": True, "pulled_at": "2026-11-19T06:00:00Z",
              "teams": {"kc": [{"player": "A", "position": "WR", "status": "Out", "injury": "Knee"}]}}
    (tmp_path / "injuries.json").write_text(json.dumps(report))
    newer = dict(report, pulled_at="2026-11-20T06:00:00Z")
    monkeypatch.setattr(update_injuries, "fetch_injury_report", lambda s, w: newer)
    assert update_injuries.main(["--data-dir", str(tmp_path)]) == 0
    assert json.loads((tmp_path / "injuries.json").read_text())["pulled_at"] == "2026-11-19T06:00:00Z"
