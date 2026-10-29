"""Unit tests for export_games.py (NBA game-page exporter). Run directly or via pytest."""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from export_games import ft_made, game_points, sec_left, shot_value

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
