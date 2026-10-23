"""PocketPicks predictor: last-5 win-rate differential -> home-win probability.

Coefficients come from the repo's trained logistic model
(see project_log/2026_09_07.md). They are fixed; this module never retrains.

    logit P(home_win) = B0 + B1 * diff
    diff = home_last5_win_rate - away_last5_win_rate
"""
import math

B0 = 0.3271  # intercept (home-field advantage)
B1 = 1.8526  # last-5 win-rate differential coefficient
MODEL = f"logistic_v1 ({B0} + {B1} * diff)"


def win_prob(diff: float) -> float:
    """Raw logistic: probability the home team wins given the win-rate diff."""
    return 1.0 / (1.0 + math.exp(-(B0 + B1 * diff)))


def predict_home_win(home_last5: float, away_last5: float) -> dict:
    """Predict a game from each team's last-5 win rate (0.0-1.0)."""
    diff = home_last5 - away_last5
    home = round(win_prob(diff), 4)
    away = round(1.0 - home, 4)
    return {
        "home_win_prob": home,
        "away_win_prob": away,
        "favored": "home" if home >= 0.5 else "away",
        "diff": diff,
        "model": MODEL,
    }
