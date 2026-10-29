"""Unit tests for export_games.py (NBA game-page exporter). Run directly or via pytest."""
import os
import sqlite3
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from export_games import (anchor_tolerance, cm, export_season, ft_block, ft_made, game_points,
                          left_out_limit, make_rates, officials, place_unlocated, sec_left,
                          shooter_sides, shot_block, shot_value, team_labels)

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


# --- gates -------------------------------------------------------------------

def test_left_out_limit_is_one_percent_with_a_floor_of_three():
    assert left_out_limit(1189) == 11    # 11.89 games: 12 fails
    assert left_out_limit(1200) == 12
    assert left_out_limit(990) == 9
    assert left_out_limit(43) == 3       # a short season may leave out three
    assert left_out_limit(300) == 3
    assert left_out_limit(400) == 4


def test_anchor_tolerance_only_loosens_for_the_live_in_progress_season(monkeypatch):
    monkeypatch.setattr(config, "ERA", "live")
    monkeypatch.setattr(config, "CURRENT_SEASON", "2026-27")
    assert anchor_tolerance("2026-27") == 0.02
    assert anchor_tolerance("2025-26") == 0.005
    monkeypatch.setattr(config, "ERA", "archive")
    assert anchor_tolerance("2026-27") == 0.005


# --- helpers extracted from export_season ------------------------------------

def test_shooter_sides_joins_ft_only_players_and_flags_a_conflict():
    sh = pd.DataFrame({"player_id": [101, 201], "side": [0, 1]})
    fts = pd.DataFrame({"pid": [103, 101], "side": [0, 0]})
    assert shooter_sides(sh, fts) == {101: 0, 201: 1, 103: 0}
    assert shooter_sides(sh, pd.DataFrame({"pid": [101], "side": [1]})) is None


def test_officials():
    meta = pd.DataFrame({"ref1_id": [11, 5], "ref1_name": ["Ref A", "Ref C"],
                         "ref2_id": [12, None], "ref2_name": ["Ref B", None],
                         "ref3_id": [None, None], "ref3_name": [None, None]},
                        index=pd.Index(["g1", "g2"], name="game_id"))
    assert officials(meta, "g1") == [["11", "Ref A"], ["12", "Ref B"]]
    assert officials(meta, "g2") == [["5", "Ref C"]]
    assert officials(meta, "missing") == []


# --- export_season on a synthetic game ---------------------------------------
# Home id 1610612760 (TEAM_ABBREV says OKC) whose pbp tricode says SEA; the away team has no
# tricode in the pbp, so it falls back to TEAM_ABBREV (LAL). Seven shots: five located, two not
# (event 6 has a shot type, event 7 has none and takes its value from the pbp). Player 103 only
# shoots free throws, player 202 has no player_season row, player 102 has no
# player_game_shot_value row (all his shots are unlocated). Final 6-5.

HOME, AWAY, GID, SEASON = 1610612760, 1610612747, "0022500999", "2025-26"


def synthetic_conn(exp_101=2.2):
    conn = sqlite3.connect(":memory:")
    conn.executescript("""
        CREATE TABLE games (GAME_ID TEXT, season TEXT, GAME_DATE TIMESTAMP, home_team_id INTEGER, away_team_id INTEGER);
        CREATE TABLE shots (game_id TEXT, event_id INTEGER, player_id INTEGER, team_id INTEGER, period INTEGER,
                            seconds_remaining_in_period REAL, shot_made INTEGER, shot_x REAL, shot_y REAL, shot_type TEXT);
        CREATE TABLE shots_xfg (game_id TEXT, event_id INTEGER, xfg REAL, xpts REAL);
        CREATE TABLE player_season (player_id INTEGER, player_name TEXT, season TEXT);
        CREATE TABLE player_season_ft (player_id INTEGER, season TEXT, ftm INTEGER, fta INTEGER);
        CREATE TABLE player_game_shot_value (player_id INTEGER, game_id TEXT, season TEXT, fga INTEGER,
                                             act_fg_pts REAL, exp_fg_pts REAL);
        CREATE TABLE game_meta (game_id TEXT PRIMARY KEY, ref1_id INTEGER, ref1_name TEXT, ref2_id INTEGER,
                                ref2_name TEXT, ref3_id INTEGER, ref3_name TEXT);
    """)
    conn.execute("INSERT INTO games VALUES (?, ?, '2025-10-29 00:00:00', ?, ?)", (GID, SEASON, HOME, AWAY))
    conn.executemany("INSERT INTO shots VALUES (?,?,?,?,?,?,?,?,?,?)", [
        (GID, 1, 101, HOME, 1, 700.0, 1, -100.0, 50.0, "2PT Field Goal"),
        (GID, 2, 101, HOME, 1, 650.0, 0, 0.0, 0.0, "3PT Field Goal"),
        (GID, 3, 201, AWAY, 1, 600.0, 1, 200.0, 100.0, "3PT Field Goal"),
        (GID, 4, 202, AWAY, 2, 300.0, 1, 10.0, 20.0, "2PT Field Goal"),
        (GID, 5, 202, AWAY, 2, 200.0, 0, -10.0, 30.0, "2PT Field Goal"),
        (GID, 6, 102, HOME, 1, 500.0, 1, None, None, "3PT Field Goal"),
        (GID, 7, 102, HOME, 3, 100.0, 0, None, None, None)])
    conn.executemany("INSERT INTO shots_xfg VALUES (?,?,?,?)", [
        (GID, 1, 0.5, 1.0), (GID, 2, 0.4, 1.2), (GID, 3, 0.36, 1.08), (GID, 4, 0.6, 1.2), (GID, 5, 0.4, 0.8)])
    conn.executemany("INSERT INTO player_season VALUES (?,?,?)", [
        (101, "Alpha One", SEASON), (102, "Bravo Two", SEASON), (103, "Charlie Three", SEASON),
        (201, "Delta One", SEASON)])
    conn.executemany("INSERT INTO player_season_ft VALUES (?,?,?,?)", [(103, SEASON, 80, 100), (999, SEASON, 70, 100)])
    conn.executemany("INSERT INTO player_game_shot_value VALUES (?,?,?,?,?,?)", [
        (101, GID, SEASON, 2, 2.0, exp_101), (201, GID, SEASON, 1, 3.0, 1.08), (202, GID, SEASON, 2, 2.0, 1.2 + 0.8)])
    conn.execute("INSERT INTO game_meta VALUES (?, 11, 'Ref A', 12, 'Ref B', NULL, NULL)", (GID,))
    return conn


def synthetic_pbp(path):
    def row(**kw):
        d = {"actionNumber": 0, "period": 1, "clock": "PT12M00.00S", "teamId": 0, "teamTricode": "",
             "personId": 0, "playerName": "", "description": "", "actionType": "", "isFieldGoal": 0,
             "shotValue": 0, "scoreHome": "", "scoreAway": ""}
        d.update(kw)
        return d
    pd.DataFrame([
        row(actionNumber=1, teamId=HOME, teamTricode="SEA", personId=101, playerName="Alpha",
            actionType="Made Shot", isFieldGoal=1, shotValue=2),
        row(actionNumber=4, period=2, teamId=AWAY, personId=202, playerName="Zed",
            actionType="Made Shot", isFieldGoal=1, shotValue=2),
        row(actionNumber=7, period=3, teamId=HOME, teamTricode="SEA", personId=102, playerName="Bravo",
            actionType="Missed Shot", isFieldGoal=1, shotValue=2),
        row(actionNumber=7, period=3, teamId=AWAY, personId=201, playerName="Delta",
            description="Delta BLOCK", shotValue=2),   # same actionNumber, not a field goal
        row(actionNumber=8, period=2, clock="PT05M30.00S", teamId=HOME, teamTricode="SEA", personId=103,
            playerName="Charlie", description="Charlie Free Throw 1 of 2 (1 PTS)", actionType="Free Throw"),
        row(actionNumber=9, period=2, clock="PT05M30.00S", teamId=HOME, teamTricode="SEA", personId=103,
            playerName="Charlie", description="MISS Charlie Free Throw 2 of 2", actionType="Free Throw"),
        row(actionNumber=10, period=4, clock="PT00M00.00S", scoreHome="6", scoreAway="5", actionType="period"),
    ]).to_parquet(path)
    return {GID: path}


def test_export_season_assembles_the_contract(tmp_path):
    r = export_season(synthetic_conn(), SEASON, synthetic_pbp(tmp_path / f"{GID}.parquet"))
    assert r["excluded"] == 0 and r["total"] == 1 and r["unlocated"] == 2 and r["name_fallbacks"] == 1
    (row,) = r["rows"]
    # index row: ids as strings, the pbp's own tricode with TEAM_ABBREV as the fallback, x to 0.1
    assert {k: v for k, v in row.items() if k != "share"} == {
        "id": GID, "d": "2025-10-29", "wk": "2025-10-27", "h": str(HOME), "a": str(AWAY),
        "hl": "SEA", "al": "LAL", "s": [6, 5], "x": [6.6, 3.1]}
    assert 0 < row["share"] < 1
    game = r["chunks"]["2025-10-27"][GID]
    assert set(game) == {"p", "s", "f", "r"}
    # p rows: [pid, name, side, fga, fgPts, xFgPts, fta, ftm], by side then points. 102's two unlocated
    # shots are added at xpts (1.5 + 4/3), not at xfg; 103 only shot free throws; 202 has the pbp's name.
    assert game["p"] == [
        ["102", "Bravo Two", 0, 2, 3, 2.83, 0, 0],
        ["101", "Alpha One", 0, 2, 2, 2.2, 0, 0],
        ["103", "Charlie Three", 0, 0, 0, 0.0, 2, 1],
        ["201", "Delta One", 1, 1, 3, 1.08, 0, 0],
        ["202", "Zed", 1, 2, 2, 2.0, 0, 0]]
    # shots in play order; players are indices into p (102 -> 0, 101 -> 1, 103 -> 2, 201 -> 3, 202 -> 4)
    assert game["s"] == {
        "p": [1, 1, 3, 0, 4, 4, 0], "q": [1, 1, 1, 1, 2, 2, 3], "c": [700, 650, 600, 500, 300, 200, 100],
        "x": [-305, 0, 610, None, 30, -30, None], "y": [152, 0, 305, None, 61, 91, None],
        "m": "1011100", "v": "2333222", "e": [500, 400, 360, 500, 600, 400, 667]}
    assert game["f"] == {"p": [2, 2], "q": [2, 2], "c": [330, 330], "m": "10", "e": [783, 783]}
    assert game["r"] == [["11", "Ref A"], ["12", "Ref B"]]


def test_export_season_xfg_points_of_players_tie_to_the_side(tmp_path):
    # player 101's expected FG points are 1.0 off what his shots in shots_xfg are worth
    with pytest.raises(ValueError, match="expected FG points"):
        export_season(synthetic_conn(exp_101=3.2), SEASON, synthetic_pbp(tmp_path / f"{GID}.parquet"))
