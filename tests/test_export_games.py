"""Unit tests for export_games.py (NBA game-page exporter). Run directly or via pytest."""
import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from export_games import (cm, ft_block, ft_made, game_points, make_rates, place_unlocated,
                          sec_left, shot_block, shot_value, team_labels)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_ft_made():
    assert ft_made("MISS Curry Free Throw 1 of 2") is False
    assert ft_made("Curry Free Throw 1 of 2 (12 PTS)") is True
    assert ft_made("Free Throw 1 of 2") is False  # a miss whose line lost the name and MISS


def test_reconstructs_final():
    pbp = pd.read_parquet(os.path.join(ROOT, "cache", "pbp", "0022500100.parquet"))
    assert game_points(pbp) == (98, 110)


def test_game_points_ignores_blank_and_stale_stamps():
    pbp = pd.DataFrame({"scoreHome": ["", "0", "12", "", "30", ""],
                        "scoreAway": ["", "0", "9", "", "31", "0"]})
    assert game_points(pbp) == (30, 31)


def test_sec_left():
    assert sec_left("PT09M59.00S") == 599
    assert sec_left("PT00M40.40S") == 40  # whole seconds are enough for a shot map
    assert sec_left("PT00M40.60S") == 41
    assert sec_left("PT12M00.00S") == 720
    assert sec_left("PT00M00.00S") == 0


def test_shot_value():
    assert shot_value("3PT Field Goal") == 3
    assert shot_value("2PT Field Goal") == 2


def test_game_points_with_no_scores_is_zero():
    pbp = pd.DataFrame({"scoreHome": ["", ""], "scoreAway": ["", ""]})
    assert game_points(pbp) == (0, 0)


def test_team_labels_take_the_games_own_tricode():
    pbp = pd.DataFrame({"teamId": [1, 1, 1, 2, 2, 0, 2],
                        "teamTricode": ["SEA", "SEA ", "OKC", "LAL", "", "XXX", None]})
    assert team_labels(pbp) == {1: "SEA", 2: "LAL"}  # most common, stripped, blanks and team 0 ignored


def test_team_labels_real_games():
    cur = team_labels(pd.read_parquet(os.path.join(ROOT, "cache", "pbp", "0022500100.parquet")))
    assert cur == {1610612753: "ORL", 1610612741: "CHI"}
    # 1997-98 Seattle SuperSonics (franchise id now OKC): the feed's tricode as of that game
    old = team_labels(pd.read_parquet(os.path.join(ROOT, "cache", "pbp", "0029700024.parquet")))
    assert old[1610612760] == "SEA"


def test_make_rates_by_value():
    shots = pd.DataFrame({"value": [2, 2, 2, 2, 3, 3], "made": [1, 1, 0, 0, 1, 0]})
    assert make_rates(shots) == {2: 0.5, 3: 0.5}
    shots = pd.DataFrame({"value": [2, 3, 3, 3, 3], "made": [1, 1, 0, 0, 0]})
    assert make_rates(shots) == {2: 1.0, 3: 0.25}


def test_place_unlocated_gets_the_league_rate_and_no_coordinates():
    un = pd.DataFrame({"value": [3, 2], "made": [1, 0]})
    placed = place_unlocated(un, {2: 0.5, 3: 0.36})
    assert placed["xfg"].tolist() == [0.36, 0.5]
    assert placed["xpts"].tolist() == pytest.approx([1.08, 1.0])
    assert placed["x"].isna().all() and placed["y"].isna().all()
    assert "xfg" not in un.columns  # the input is not modified


def test_cm_nulls_unlocated():
    assert cm([float("nan"), 12.0, -3.0]) == [None, 12, -3]


def test_shot_block_is_columnar_with_a_player_index():
    sh = pd.DataFrame({"player_id": [20, 10, 20], "period": [1, 1, 5], "sec": [700, 650, 12],
                       "x": [-546.0, float("nan"), 30.0], "y": [546.0, float("nan"), 0.0],
                       "made": [0, 1, 1], "value": [3, 2, 3], "xfg": [0.3584, 0.5, 0.3604]})
    blk = shot_block(sh, {10: 0, 20: 1})
    assert blk == {"p": [1, 0, 1], "q": [1, 1, 5], "c": [700, 650, 12],
                   "x": [-546, None, 30], "y": [546, None, 0],
                   "m": "011", "v": "323", "e": [358, 500, 360]}


def test_ft_block_is_columnar():
    fts = pd.DataFrame({"pid": [10, 10, 20], "period": [2, 2, 4], "sec": [90, 90, 3],
                        "made": [True, False, True], "pct": [0.7634, 0.7634, 0.5]})
    blk = ft_block(fts, {10: 0, 20: 1})
    assert blk == {"p": [0, 0, 1], "q": [2, 2, 4], "c": [90, 90, 3], "m": "101", "e": [763, 763, 500]}
    assert ft_block(fts.iloc[:0], {}) == {"p": [], "q": [], "c": [], "m": "", "e": []}
