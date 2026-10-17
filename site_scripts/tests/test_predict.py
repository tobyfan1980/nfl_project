"""Tests for the PocketPicks logistic predictor (site_scripts/predict.py)."""
import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from predict import predict_home_win, win_prob  # noqa: E402

MODEL = "logistic_v1 (0.3271 + 1.8526 * diff)"


def test_win_prob():
    assert abs(win_prob(0.0) - 0.5811) < 1e-3
    assert win_prob(0.0) == pytest.approx(1 / (1 + math.exp(-0.3271)))
    # 0.5 decision boundary: diff = -B0 / B1 = -0.1766
    assert win_prob(-0.1766) == pytest.approx(0.5, abs=1e-3)


def test_win_prob_monotonic():
    assert win_prob(-1.0) < win_prob(0.0) < win_prob(1.0)


def test_predict_home_win_favored():
    r = predict_home_win(0.8, 0.4)
    assert r["favored"] == "home"
    assert r["diff"] == pytest.approx(0.4)
    assert r["home_win_prob"] > 0.5
    assert r["home_win_prob"] + r["away_win_prob"] == pytest.approx(1.0)
    assert r["model"] == MODEL
    assert set(r) == {"home_win_prob", "away_win_prob", "favored", "diff", "model"}


def test_predict_home_win_away_favored():
    r = predict_home_win(0.2, 0.8)
    assert r["favored"] == "away"
    assert r["away_win_prob"] > 0.5
    assert r["home_win_prob"] + r["away_win_prob"] == pytest.approx(1.0)


def test_predict_home_win_even_matchup_favors_home():
    # Equal records: home-field intercept gives home ~0.5811.
    r = predict_home_win(0.6, 0.6)
    assert r["favored"] == "home"
    assert r["home_win_prob"] == pytest.approx(0.5811, abs=1e-4)


def test_predict_home_win_rounded_to_4dp():
    r = predict_home_win(0.8, 0.4)
    assert r["home_win_prob"] == round(r["home_win_prob"], 4)
    assert r["away_win_prob"] == round(r["away_win_prob"], 4)
