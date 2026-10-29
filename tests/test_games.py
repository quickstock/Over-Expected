"""Unit tests for games.py (shared per-game math). Run directly or via pytest."""
import datetime as dt

import numpy as np
import pandas as pd
import pytest

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from games import week_key, shrunk_ft_pct, side_totals, win_share, calibration

EMPTY_FTS = pd.DataFrame({"side": [], "made": [], "pct": []})


def test_week_key():
    assert week_key(dt.date(2026, 10, 29)) == "2026-10-26"
    assert week_key(dt.date(2026, 10, 26)) == "2026-10-26"


def test_shrunk_ft_pct():
    assert shrunk_ft_pct(0, 0, 0.77) == pytest.approx(0.77)
    assert shrunk_ft_pct(90, 100, 0.77) == pytest.approx((90 + 50 * 0.77) / 150)


def test_side_totals():
    shots = pd.DataFrame({"side": [0, 0], "value": [2, 3], "made": [1, 0], "xfg": [0.5, 0.4]})
    fts = pd.DataFrame({"side": [0, 0], "made": [1, 0], "pct": [0.8, 0.8]})
    t = side_totals(shots, fts)
    assert t[0] == pytest.approx({"fg": 2, "xfg": 2.2, "ftm": 1, "xft": 1.6})
    assert t[1] == {"fg": 0, "xfg": 0, "ftm": 0, "xft": 0}


def test_win_share_bounds_and_ties():
    sure = pd.DataFrame({"side": [0, 1], "value": [2, 2], "made": [1, 0], "xfg": [1.0, 0.0]})
    assert win_share(sure, EMPTY_FTS, seed=1) == 1.0
    tie = pd.DataFrame({"side": [0, 1], "value": [2, 2], "made": [1, 1], "xfg": [1.0, 1.0]})
    assert win_share(tie, EMPTY_FTS, seed=1) == 0.5


def test_win_share_symmetric_and_seeded():
    rng = np.random.default_rng(0)
    shots = pd.DataFrame({"side": np.repeat([0, 1], 80), "value": 2, "made": 0,
                          "xfg": np.tile(rng.uniform(0.3, 0.6, 80), 2)})
    a = win_share(shots, EMPTY_FTS, seed=7)
    assert a == win_share(shots, EMPTY_FTS, seed=7)
    assert abs(a - 0.5) < 0.03


def test_calibration():
    rng = np.random.default_rng(3)
    p = rng.uniform(0, 1, 20_000)
    bins, ece = calibration(p, rng.uniform(0, 1, 20_000) < p)
    assert len(bins) == 10 and ece < 0.02
    assert calibration(p, np.ones(20_000, bool))[1] > 0.3
