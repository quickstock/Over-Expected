"""The shot-value suite — Gate 2. Combine xFG% (make value) with xFTA
(foul-drawing value) into expected points per shot, then player-season
leaderboards.

Shot quality (look value, shooter-agnostic):
    xPoints = xFG% * (2 or 3) + xFTA * league_FT%
    (league_FT% = the season's actual league free-throw make rate)

The headline "points over expected" credits both halves symmetrically — actual
conversion above the look on BOTH the field-goal side and the free-throw side:

  shot-making over expected = actual FG% - xFG%            (FG conversion skill)
  shot-selection value      = mean xPoints of looks taken  (look quality)
  combined POE / 100 poss   = (actual FG pts - expected FG pts)              # FG side
                              + (actual FTA * own FT% - xFTA * league FT%)   # FT side

The FT side is the option-B fix for the earlier asymmetry: the old version
valued both actual and expected FTAs at a flat league rate, which cancels
out free-throw shooting skill while the FG side fully credited it. Now each
player's drawn free throws are valued at HIS season FT% (player_season_ft),
so a 65% Giannis no longer gets league-average credit for trips a 90% shooter
banks. Expected FTAs are valued at the season's actual league FT% — the
league-neutral baseline.
(Approximation: season FT% covers all foul types; actual_fta here is shooting
fouls only. A player's FT% barely varies by foul type, so this is fine.)

Consistency: xFG% is the leakage-free SEASON CROSS-FIT of the Gate 1 model
(train on the other seasons, predict each season). The xFTA side reuses the
published clean possession-level board (player_season_xfta_poss_lb_clean),
so this sits exactly alongside the live FTAOE leaderboard.

v1 simplification (flagged, not over-engineered): the make term and the
foul term are summed independently. On an and-1 a player legitimately earns
both the made bucket and the bonus FT, which the sum captures; but the two
models are not jointly conditioned on "made shot given a foul". Small, named.
"""
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

from config import DB_PATH
from xfg_model import engineer, make_clf, FEATURES

QUALIFY_POSS = 300      # same qualification as the xFTA board
LEADERBOARD_SEASON = "2024-25"   # latest complete season for the top-25


def load_all() -> pd.DataFrame:
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql(
        """SELECT s.game_id, s.player_id, s.team_id, s.period,
                  s.seconds_remaining_in_period, s.shot_made,
                  s.shot_x, s.shot_y, s.shot_distance,
                  s.shot_zone_basic, s.shot_zone_area,
                  s.action_type, s.shot_type, s.score_margin, g.season,
                  m.home_team_id, m.away_team_id
           FROM shots s JOIN games g ON g.GAME_ID = s.game_id
           JOIN game_meta m ON m.game_id = s.game_id
           WHERE s.shot_zone_basic IS NOT NULL AND s.shot_zone_basic != ''
             AND s.shot_x IS NOT NULL AND s.shot_y IS NOT NULL""",
        conn,
    )
    conn.close()
    return df


def cross_fit_xfg(df: pd.DataFrame) -> pd.Series:
    """Leakage-free xFG%: for each season, train on every other season."""
    import time
    xfg = pd.Series(np.nan, index=df.index)
    seasons = sorted(df["season"].unique())
    for s in seasons:
        tr = df[df["season"] != s]
        te = df[df["season"] == s]
        t0 = time.monotonic()
        clf = make_clf()
        clf.fit(tr[FEATURES], tr["shot_made"])
        xfg.loc[te.index] = clf.predict_proba(te[FEATURES])[:, 1]
        print(f"  fold {s}: trained on {len(tr):,}, scored {len(te):,} "
              f"({time.monotonic() - t0:.0f}s)")
    return xfg


def main() -> None:
    df = engineer(load_all())
    print(f"loaded {len(df):,} FGA across {df['season'].nunique()} seasons")

    print("season cross-fit xFG%:")
    df["xfg"] = cross_fit_xfg(df)

    # SEASON ANCHORING, mirroring the xFTA side: a model trained on the
    # other five seasons inherits their league-wide make rate, so each
    # held-out season's mean xFG% lands offset from its own actual FG%
    # (the 2021-22 shooting dip alone was worth -1.7 FG pts over
    # expected per 100 league-wide). Scale each season's xFG so its mean
    # equals that season's actual FG% — league sits at zero by
    # construction, same invariant the FTAOE board guarantees.
    chk = df.groupby("season").agg(
        actual=("shot_made", "mean"), xfg=("xfg", "mean"), n=("shot_made", "size"))
    anchors = chk["actual"] / chk["xfg"]
    df["xfg"] = df["xfg"] * df["season"].map(anchors)
    print("\nper-season anchoring (mean xFG% scaled to actual FG%):")
    print(chk.assign(anchor=anchors).round(
        {"actual": 4, "xfg": 4, "anchor": 4}).to_string())

    pts = np.where(df["shot_type"].str.contains("3"), 3, 2)
    df["exp_fg_pts"] = df["xfg"] * pts
    df["act_fg_pts"] = df["shot_made"] * pts

    # Per-(player, game) FG points: the schedule-order series the player page
    # draws as the shot-value / shot-making gap and form charts.
    per_game_fg = (
        df.groupby(["player_id", "game_id", "season"])
        .agg(fga=("shot_made", "size"), fgm=("shot_made", "sum"),
             act_fg_pts=("act_fg_pts", "sum"), exp_fg_pts=("exp_fg_pts", "sum"))
        .reset_index()
    )
    per_game_fg["act_fg_pts"] = per_game_fg["act_fg_pts"].round(3)
    per_game_fg["exp_fg_pts"] = per_game_fg["exp_fg_pts"].round(3)

    # Team-level FG points over expected, both sides: offense by the shooting
    # team, defense by the opponent (points the defense allowed over expected).
    # Per-100 normalization happens in the export against team possessions.
    df["def_team_id"] = np.where(
        df["team_id"] == df["home_team_id"], df["away_team_id"], df["home_team_id"])
    off_t = (df.groupby(["team_id", "season"])
             .agg(off_fga=("shot_made", "size"), off_act_fg_pts=("act_fg_pts", "sum"),
                  off_exp_fg_pts=("exp_fg_pts", "sum")).reset_index()
             .rename(columns={"team_id": "team_id"}))
    def_t = (df.groupby(["def_team_id", "season"])
             .agg(def_fga=("shot_made", "size"), def_act_fg_pts=("act_fg_pts", "sum"),
                  def_exp_fg_pts=("exp_fg_pts", "sum")).reset_index()
             .rename(columns={"def_team_id": "team_id"}))
    team_sv = off_t.merge(def_t, on=["team_id", "season"], how="outer")
    for c in ["off_act_fg_pts", "off_exp_fg_pts", "def_act_fg_pts", "def_exp_fg_pts"]:
        team_sv[c] = team_sv[c].round(2)

    agg = (
        df.groupby(["player_id", "season"])
        .agg(fga=("shot_made", "size"), fgm=("shot_made", "sum"),
             exp_makes=("xfg", "sum"), exp_fg_pts=("exp_fg_pts", "sum"),
             act_fg_pts=("act_fg_pts", "sum"))
        .reset_index()
    )

    # Join the published clean xFTA board for the foul-drawing side.
    conn = sqlite3.connect(DB_PATH)
    board = pd.read_sql(
        """SELECT player_id, season, player_name, position, possessions,
                  actual_fta_from_fouls AS actual_fta, xfta_total, ftaoe
           FROM player_season_xfta_poss_lb_clean""",
        conn,
    )
    board["player_id"] = board["player_id"].astype(int)
    sv = agg.merge(board, on=["player_id", "season"], how="inner")

    # Each player's own season FT% for the FT-conversion credit (option B).
    ft = pd.read_sql(
        "SELECT player_id, season, ftm, fta, ft_pct FROM player_season_ft", conn)
    ft["player_id"] = ft["player_id"].astype(int)
    # The league baseline is each season's ACTUAL league FT% (FTA-weighted),
    # not a flat constant — 0.77 vs the true ~0.78 was handing the whole
    # league ~+0.1 to +0.3 free FT points per 100.
    league_ft = ft.groupby("season").apply(lambda g: g["ftm"].sum() / g["fta"].sum())
    print("\nseason league FT% baseline:")
    print(league_ft.round(4).to_string())
    sv = sv.merge(ft[["player_id", "season", "ft_pct"]],
                  on=["player_id", "season"], how="left")
    sv["league_ft"] = sv["season"].map(league_ft)
    # No FT% on record (never shot a free throw) -> fall back to league rate.
    sv["ft_pct"] = sv["ft_pct"].where(sv["ft_pct"] > 0, sv["league_ft"])

    # Metrics.
    sv["fg_pct"] = sv["fgm"] / sv["fga"]
    sv["xfg_pct"] = sv["exp_makes"] / sv["fga"]
    sv["shot_making_oe"] = (sv["fg_pct"] - sv["xfg_pct"]) * 100          # pp
    sv["xpoints_per_shot"] = (sv["exp_fg_pts"] + sv["xfta_total"] * sv["league_ft"]) / sv["fga"]
    sv["fg_pts_oe"] = sv["act_fg_pts"] - sv["exp_fg_pts"]
    # FT points over expected: drawn FTs banked at the player's own FT%,
    # expected FTs valued at the season's league-average FT%.
    sv["ft_pts_oe"] = sv["actual_fta"] * sv["ft_pct"] - sv["xfta_total"] * sv["league_ft"]
    sv["points_oe"] = sv["fg_pts_oe"] + sv["ft_pts_oe"]
    sv["fg_pts_oe_per100"] = sv["fg_pts_oe"] / sv["possessions"] * 100
    sv["ft_pts_oe_per100"] = sv["ft_pts_oe"] / sv["possessions"] * 100
    sv["points_oe_per100"] = sv["points_oe"] / sv["possessions"] * 100

    for c in ["fg_pct", "xfg_pct", "shot_making_oe", "xpoints_per_shot",
              "exp_fg_pts", "act_fg_pts", "fg_pts_oe", "ft_pts_oe",
              "points_oe", "points_oe_per100", "fg_pts_oe_per100",
              "ft_pts_oe_per100", "xfta_total", "ftaoe", "ft_pct"]:
        sv[c] = sv[c].round(4)

    # Write the suite table into the DB.
    out_cols = [
        "player_id", "player_name", "season", "position", "possessions",
        "fga", "fgm", "fg_pct", "xfg_pct", "shot_making_oe",
        "xpoints_per_shot", "exp_fg_pts", "act_fg_pts", "fg_pts_oe",
        "fg_pts_oe_per100", "actual_fta", "xfta_total", "ftaoe", "ft_pct",
        "ft_pts_oe", "ft_pts_oe_per100", "points_oe", "points_oe_per100",
    ]
    sv[out_cols].to_sql("shot_value", conn, if_exists="replace", index=False)
    per_game_fg.to_sql("player_game_shot_value", conn, if_exists="replace", index=False)
    team_sv.to_sql("team_shot_value", conn, if_exists="replace", index=False)
    conn.close()
    print(f"\nwrote shot_value table: {len(sv):,} player-seasons")
    print(f"wrote player_game_shot_value: {len(per_game_fg):,} player-games")
    print(f"wrote team_shot_value: {len(team_sv):,} team-seasons")

    # Combined shot-value leaderboard — top 25, latest complete season.
    q = sv[(sv["season"] == LEADERBOARD_SEASON) & (sv["possessions"] >= QUALIFY_POSS)]
    top = q.sort_values("points_oe_per100", ascending=False).head(25)
    show = top[[
        "player_name", "fga", "fg_pct", "xfg_pct", "shot_making_oe",
        "xpoints_per_shot", "ftaoe", "points_oe_per100",
    ]].copy()
    show.columns = ["player", "FGA", "FG%", "xFG%", "make_oe_pp",
                    "xPts/shot", "FTAOE", "POE/100"]
    show["FG%"] = (show["FG%"] * 100).round(1)
    show["xFG%"] = (show["xFG%"] * 100).round(1)
    show = show.round({"make_oe_pp": 1, "xPts/shot": 3, "FTAOE": 1, "POE/100": 2})
    pd.set_option("display.width", 200)
    print(f"\n=== Combined shot-value leaderboard — {LEADERBOARD_SEASON}, "
          f"top 25 by points over expected / 100 poss (>= {QUALIFY_POSS} poss) ===")
    print(show.to_string(index=False))


if __name__ == "__main__":
    main()
