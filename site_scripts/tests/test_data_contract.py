"""Pins the PocketPicks JSON data contract documented in site/data/README.md.

Every canonical fixture in site_scripts/tests/fixtures/data/ must match the
contract, and the accuracy tallies must be derivable from results.json. The
fixtures are copies of the hand-written examples (decoupled from the live
site/data/ files, which update_week.py overwrites with real data); only the
contract document itself (site/data/README.md) is read from site/data/.
"""
import json
import math
import re
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "fixtures" / "data"
README_PATH = Path(__file__).resolve().parents[2] / "site" / "data" / "README.md"

GAME_ID_RE = re.compile(r"^(\d{4})-W(\d{2})-([a-z]+)-([a-z]+)$")
ISO_UTC_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
SCORE_RE = re.compile(r"^\d+-\d+$")
MODEL = "logistic_v1 (0.3271 + 1.8526 * diff)"
SIDES = {"home", "away"}


def load(name):
    with open(DATA_DIR / name, encoding="utf-8") as f:
        return json.load(f)


def is_number(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def check_keys(obj, required, label):
    assert isinstance(obj, dict), f"{label} must be an object"
    assert set(obj) == set(required), f"{label} keys {sorted(obj)} != {sorted(required)}"


def check_result(r, label):
    check_keys(r, {"opponent", "result", "score", "home_away"}, label)
    assert isinstance(r["opponent"], str) and r["opponent"].islower()
    assert r["result"] in {"W", "L", "T"}
    assert SCORE_RE.match(r["score"])
    assert r["home_away"] in SIDES


def check_team(t, label):
    check_keys(t, {"team", "slug", "record", "streak"}, label)
    assert isinstance(t["team"], str) and t["team"]
    assert re.fullmatch(r"[a-z]+", t["slug"])
    assert re.fullmatch(r"\d+-\d+(-\d+)?", t["record"])
    assert re.fullmatch(r"[WLT]\d+", t["streak"])


def check_prediction(p, label):
    check_keys(
        p,
        {"home_win_prob", "away_win_prob", "favored", "home_last5_win_rate",
         "away_last5_win_rate", "diff", "model"},
        label,
    )
    for k in ("home_win_prob", "away_win_prob", "home_last5_win_rate",
              "away_last5_win_rate", "diff"):
        assert is_number(p[k]), f"{label}.{k} must be a number"
    assert p["model"] == MODEL
    assert p["favored"] in SIDES
    assert math.isclose(p["home_win_prob"] + p["away_win_prob"], 1.0, abs_tol=1e-9)
    assert p["favored"] == ("home" if p["home_win_prob"] > p["away_win_prob"] else "away")
    assert math.isclose(
        p["diff"], p["home_last5_win_rate"] - p["away_last5_win_rate"], abs_tol=1e-9
    )
    # The pinned logistic model; fixture probabilities are rounded to 2 places.
    expected = 1 / (1 + math.exp(-(0.3271 + 1.8526 * p["diff"])))
    assert abs(p["home_win_prob"] - expected) <= 0.006, (
        f"{label}: home_win_prob {p['home_win_prob']} does not match model {expected:.4f}"
    )


def check_odds(o, label):
    check_keys(o, {"home_moneyline", "away_moneyline", "books", "source", "pulled_at"}, label)
    assert isinstance(o["home_moneyline"], int) and not isinstance(o["home_moneyline"], bool)
    assert isinstance(o["away_moneyline"], int) and not isinstance(o["away_moneyline"], bool)
    assert isinstance(o["books"], int) and o["books"] > 0
    assert isinstance(o["source"], str) and o["source"]
    assert ISO_UTC_RE.match(o["pulled_at"])


def test_season_json_matches_contract():
    season = load("season.json")
    check_keys(season, {"season", "current_week", "model_active_from_week"}, "season.json")
    for v in season.values():
        assert isinstance(v, int) and not isinstance(v, bool)
    assert 1 <= season["current_week"] <= 18
    assert season["model_active_from_week"] >= 2


def test_week_files_match_contract():
    week_files = sorted(DATA_DIR.glob("week_*.json"))
    assert week_files, "expected at least one week_NN.json fixture"
    for path in week_files:
        week_file = load(path.name)
        check_keys(week_file, {"season", "week", "generated_at", "games"}, path.name)
        assert path.name == f"week_{week_file['week']:02d}.json"
        assert ISO_UTC_RE.match(week_file["generated_at"])
        assert week_file["games"], f"{path.name} has no games"

        seen_ids = set()
        for g in week_file["games"]:
            label = f"{path.name}:{g.get('id')}"
            check_keys(
                g,
                {"id", "kickoff_utc", "home", "away", "prediction", "odds",
                 "last5_home", "last5_away"},
                label,
            )
            check_team(g["home"], f"{label}.home")
            check_team(g["away"], f"{label}.away")

            # id = {season}-W{week:02d}-{home_slug}-{away_slug}, lowercase, home first
            expected_id = (
                f"{week_file['season']}-W{week_file['week']:02d}"
                f"-{g['home']['slug']}-{g['away']['slug']}"
            )
            assert g["id"] == expected_id
            assert GAME_ID_RE.match(g["id"])
            assert g["id"] not in seen_ids
            seen_ids.add(g["id"])

            assert ISO_UTC_RE.match(g["kickoff_utc"])
            if g["prediction"] is not None:
                check_prediction(g["prediction"], f"{label}.prediction")
            if g["odds"] is not None:
                check_odds(g["odds"], f"{label}.odds")
            for key in ("last5_home", "last5_away"):
                assert isinstance(g[key], list) and len(g[key]) <= 5
                for i, r in enumerate(g[key]):
                    check_result(r, f"{label}.{key}[{i}]")


def test_week_07_covers_every_game_shape():
    games = load("week_07.json")["games"]
    assert len(games) == 3
    favored = {g["prediction"]["favored"] for g in games if g["prediction"]}
    assert favored == {"home", "away"}
    warming_up = [g for g in games if g["prediction"] is None]
    assert len(warming_up) == 1 and warming_up[0]["odds"] is None


def test_results_match_contract():
    results = load("results.json")
    assert results
    for gid, r in results.items():
        m = GAME_ID_RE.match(gid)
        assert m, f"bad game id {gid}"
        check_keys(r, {"season", "week", "final", "winner", "picked", "correct"}, gid)
        assert r["season"] == int(m.group(1)) and r["week"] == int(m.group(2))
        assert SCORE_RE.match(r["final"])
        home_pts, away_pts = map(int, r["final"].split("-"))
        assert r["winner"] == ("home" if home_pts > away_pts else "away")
        assert r["picked"] in SIDES | {None}
        if r["picked"] is None:
            assert r["correct"] is None
        else:
            assert isinstance(r["correct"], bool)
            assert r["correct"] == (r["picked"] == r["winner"])


def test_accuracy_matches_contract_shape():
    acc = load("accuracy.json")
    check_keys(acc, {"season", "weeks", "overall"}, "accuracy.json")
    assert isinstance(acc["season"], int)
    week_keys = {"week", "correct", "total", "pct", "cumulative_correct",
                 "cumulative_total", "cumulative_pct"}
    for w in acc["weeks"]:
        check_keys(w, week_keys, f"accuracy week {w.get('week')}")
    check_keys(acc["overall"], {"correct", "total", "pct", "record"}, "accuracy.overall")
    assert re.fullmatch(r"\d+-\d+", acc["overall"]["record"])


def test_accuracy_totals_equal_results_sums():
    results = load("results.json")
    acc = load("accuracy.json")

    judged = {gid: r for gid, r in results.items() if r["correct"] is not None}
    per_week = {}
    for r in judged.values():
        bucket = per_week.setdefault(r["week"], [0, 0])
        bucket[0] += r["correct"]
        bucket[1] += 1

    assert [w["week"] for w in acc["weeks"]] == sorted(per_week)

    cum_correct = cum_total = 0
    for w in acc["weeks"]:
        correct, total = per_week[w["week"]]
        cum_correct += correct
        cum_total += total
        assert (w["correct"], w["total"]) == (correct, total)
        assert w["pct"] == round(correct / total, 4)
        assert (w["cumulative_correct"], w["cumulative_total"]) == (cum_correct, cum_total)
        assert w["cumulative_pct"] == round(cum_correct / cum_total, 4)

    overall = acc["overall"]
    assert overall["correct"] == sum(1 for r in results.values() if r["correct"] is True)
    assert overall["total"] == len(judged)
    assert overall["pct"] == round(overall["correct"] / overall["total"], 4)
    assert overall["record"] == f"{overall['correct']}-{overall['total'] - overall['correct']}"
    assert acc["season"] == load("season.json")["season"]


def test_results_cover_week_07_fixture_games():
    results = load("results.json")
    for g in load("week_07.json")["games"]:
        r = results[g["id"]]
        pred = g["prediction"]
        assert r["picked"] == (pred["favored"] if pred else None)


def test_injuries_match_contract():
    inj = load("injuries.json")
    assert isinstance(inj["available"], bool)
    assert ISO_UTC_RE.match(inj["pulled_at"])
    assert isinstance(inj["teams"], dict)
    if inj["available"]:
        assert set(inj) == {"available", "pulled_at", "teams"}
        assert len(inj["teams"]) >= 2
        for slug, entries in inj["teams"].items():
            assert re.fullmatch(r"[a-z]+", slug)
            for e in entries:
                check_keys(e, {"player", "position", "status", "injury"}, f"injuries.{slug}")
                assert e["status"] in {"Out", "Doubtful", "Questionable"}
                assert all(isinstance(v, str) and v for v in e.values())
    else:
        assert set(inj) == {"available", "pulled_at", "reason", "teams"}
        assert inj["teams"] == {}


def test_fixtures_match_contract():
    """Umbrella check: every contract file exists and is valid JSON."""
    assert README_PATH.is_file(), "missing site/data/README.md"
    for name in ("season.json", "week_07.json", "results.json",
                 "accuracy.json", "injuries.json"):
        assert (DATA_DIR / name).is_file(), f"missing {name}"
    for name in ("season.json", "week_07.json", "results.json",
                 "accuracy.json", "injuries.json"):
        load(name)
