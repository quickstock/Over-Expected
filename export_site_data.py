"""Export the leak-free xFTA tables into static JSON for the website.

Sources (all clean / leak-free):
  - player_season_xfta_poss_lb_clean  -> leaderboard
  - possessions + predictions_poss_clean + games -> per-player per-game
    [actual, expected, possessions] series (game index order = game_id order)
  - training_fga + shots -> charged-FGA shot zones per player-season
  - predictions_poss_clean -> league distribution inputs + calibration bins

Output (chunked so the initial load stays small as seasons grow):
  site/public/data.json              core: meta, leaderboard, distributions,
                                     leagueZones, calibration
  site/public/players-{season}.json  per-season player detail (games, zones),
                                     fetched on demand by player pages
"""
import json
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

from config import ARTIFACT_DIR, DB_PATH, EXPORT_DIR
import referees

QUALIFY_POSS = 300  # threshold for percentile + player pages
OUT = Path(EXPORT_DIR) / "data.json"

from config import TEAM_ABBREV  # noqa: E402

conn = sqlite3.connect(DB_PATH)

# ---------------------------------------------------------------- leaderboard
# All rows from the clean table: the UI handles the min-possession filter.
lb = pd.read_sql(
    """SELECT player_id, season, possessions, actual_fta_from_fouls,
              xfta_total, ftaoe, ftaoe_per_100, player_name, position
       FROM player_season_xfta_poss_lb_clean""",
    conn,
)
lb["player_id"] = lb["player_id"].astype(int)

# percentile of ftaoe_per_100 within season among qualified players
def add_percentile(df: pd.DataFrame) -> pd.DataFrame:
    q = df["possessions"] >= QUALIFY_POSS
    df = df.copy()
    df["pct"] = np.nan
    for season, grp in df[q].groupby("season"):
        ranks = grp["ftaoe_per_100"].rank(pct=True) * 100
        df.loc[ranks.index, "pct"] = ranks
    return df

lb = add_percentile(lb)

# Style-adjusted FTAOE (second baseline: exposure-only attack profile).
style = pd.read_sql("SELECT player_id, season, style_xfta FROM style_expected", conn)
style["player_id"] = style["player_id"].astype(int)
lb = lb.merge(style, on=["player_id", "season"], how="left")
lb["sadj_per100"] = (
    (lb["actual_fta_from_fouls"] - lb["style_xfta"]) / lb["possessions"] * 100
)
lb["spct"] = np.nan
mask = lb["style_xfta"].notna() & (lb["possessions"] >= QUALIFY_POSS)
for season, grp in lb[mask].groupby("season"):
    ranks = grp["sadj_per100"].rank(pct=True) * 100
    lb.loc[ranks.index, "spct"] = ranks

# Teams a player finished possessions for, in first-appearance order.
# Derived from possessions.offense_team_id; id 0 is a parsing artifact, skipped.
team_rows = pd.read_sql(
    """SELECT p.finisher_player_id AS player_id, g.season,
              p.offense_team_id AS team_id, MIN(p.game_id) AS first_game
       FROM possessions p
       JOIN games g ON g.GAME_ID = p.game_id
       WHERE p.finisher_player_id IS NOT NULL AND p.offense_team_id > 0
       GROUP BY p.finisher_player_id, g.season, p.offense_team_id""",
    conn,
)
unknown = set(team_rows["team_id"]) - set(TEAM_ABBREV)
if unknown:
    raise SystemExit(f"Unmapped team ids in possessions: {unknown}")
team_rows["player_id"] = team_rows["player_id"].astype(int)
team_rows = team_rows.sort_values("first_game")
teams_by_key: dict[tuple[int, str], list[str]] = {}
for r in team_rows.itertuples():
    teams_by_key.setdefault((r.player_id, r.season), []).append(
        TEAM_ABBREV[r.team_id]
    )

leaderboard = [
    {
        "id": int(r.player_id),
        "name": r.player_name,
        "season": r.season,
        "pos": (r.position or "").split("-")[0] or None,
        "teams": teams_by_key.get((int(r.player_id), r.season), []),
        "poss": int(r.possessions),
        "fta": int(r.actual_fta_from_fouls),
        # xfta rounded to 2dp; ftaoe derived from the rounded value so the
        # identity ftaoe == fta - xfta holds exactly inside this file.
        "xfta": round(r.xfta_total, 2),
        "ftaoe": round(r.actual_fta_from_fouls - round(r.xfta_total, 2), 2),
        "per100": round(r.ftaoe_per_100, 2),
        "pct": round(r.pct, 1) if pd.notna(r.pct) else None,
        "sper100": round(r.sadj_per100, 2) if pd.notna(r.sadj_per100) else None,
        "spct": round(r.spct, 1) if pd.notna(r.spct) else None,
    }
    for r in lb.itertuples()
]

# league distribution: per-100 values for qualified players, per season
distributions = {
    season: sorted(
        round(v, 2)
        for v in grp.loc[grp["possessions"] >= QUALIFY_POSS, "ftaoe_per_100"]
    )
    for season, grp in lb.groupby("season")
}

# ------------------------------------------------- per-game cumulative series
qualified = lb[lb["possessions"] >= QUALIFY_POSS][["player_id", "season"]]
qual_keys = set(zip(qualified["player_id"], qualified["season"]))

per_game = pd.read_sql(
    """SELECT p.finisher_player_id AS player_id, g.season, p.game_id,
              SUM(p.sfta) AS actual, COUNT(*) AS poss
       FROM possessions p
       JOIN games g ON g.GAME_ID = p.game_id
       WHERE p.finisher_player_id IS NOT NULL
       GROUP BY p.finisher_player_id, g.season, p.game_id
       ORDER BY p.game_id""",
    conn,
)
per_game["player_id"] = per_game["player_id"].astype(int)
# Expected FTs per game from the shot-diet baseline; a game's expectation
# comes from that game's attempts, so a player's games sum to his season.
diet_game = pd.read_sql(
    "SELECT game_id, player_id, xft AS xfta FROM diet_game", conn)
diet_game["player_id"] = diet_game["player_id"].astype(int)
per_game = per_game.merge(diet_game, on=["game_id", "player_id"], how="left")
per_game["xfta"] = per_game["xfta"].fillna(0.0)

# Per-(player, game) FG points from the shot-value suite, to enrich each game
# tuple with the shot-making side. Absent if shot_value.py hasn't run.
fg_by_key: dict[tuple, tuple] = {}
if conn.execute(
    "SELECT name FROM sqlite_master WHERE type='table' AND name='player_game_shot_value'"
).fetchone():
    pgfg = pd.read_sql(
        "SELECT player_id, game_id, season, act_fg_pts, exp_fg_pts "
        "FROM player_game_shot_value", conn)
    fg_by_key = {
        (int(r.player_id), r.game_id, r.season): (
            round(float(r.act_fg_pts), 2), round(float(r.exp_fg_pts), 2))
        for r in pgfg.itertuples()
    }

# ------------------------------------------------------- charged-FGA zones
zones = pd.read_sql(
    """SELECT t.player_id, t.season, s.shot_zone_basic AS zone,
              s.shot_zone_area AS area, COUNT(*) AS n
       FROM training_fga t
       JOIN shots s ON s.game_id = t.game_id AND s.event_id = t.event_id
       WHERE s.shot_zone_basic IS NOT NULL AND s.shot_zone_basic != ''
       GROUP BY t.player_id, t.season, s.shot_zone_basic, s.shot_zone_area""",
    conn,
)

# league zone shares per season (for "vs league" comparison)
league_zones = (
    zones.groupby(["season", "zone", "area"])["n"].sum().reset_index()
)
league_zone_out = {}
for season, grp in league_zones.groupby("season"):
    total = grp["n"].sum()
    league_zone_out[season] = [
        {"zone": r.zone, "area": r.area, "share": round(r.n / total, 4)}
        for r in grp.itertuples()
    ]

# ----------------------------------------------------- shooting-foul detail
# FT counts by trip type (identity: and1+sf2+sf3 == actual FTA), plus the
# located and-1 shots for the foul-origin court view.
fouls_agg = pd.read_sql(
    """SELECT p.finisher_player_id AS player_id, g.season,
              SUM(p.ft_and1) AS and1, SUM(p.ft_sf2) AS sf2,
              SUM(p.ft_sf3) AS sf3
       FROM possessions p
       JOIN games g ON g.GAME_ID = p.game_id
       WHERE p.finisher_player_id IS NOT NULL
       GROUP BY p.finisher_player_id, g.season""",
    conn,
)
fouls_agg["player_id"] = fouls_agg["player_id"].astype(int)
fouls_by_key = {
    (int(r.player_id), r.season): (int(r.and1), int(r.sf2), int(r.sf3))
    for r in fouls_agg.itertuples()
}

# Only and-1s where the shot maker also finished the possession (the FT
# counts above attribute whole possessions to the finisher; ~0.2% of and-1
# events belong to multi-trip possessions finished by a teammate and are
# dropped here so located <= and1 holds per player).
and1_zones = pd.read_sql(
    """SELECT a.player_id, g.season, s.shot_zone_basic AS zone,
              s.shot_zone_area AS area, COUNT(*) AS n
       FROM and1_shots a
       JOIN games g ON g.GAME_ID = a.game_id
       JOIN possessions p
         ON p.game_id = a.game_id
        AND p.possession_number = a.possession_number
        AND p.finisher_player_id = a.player_id
       JOIN shots s ON s.game_id = a.game_id AND s.event_id = a.event_id
       WHERE s.shot_zone_basic IS NOT NULL AND s.shot_zone_basic != ''
       GROUP BY a.player_id, g.season, s.shot_zone_basic, s.shot_zone_area""",
    conn,
)
and1_zones["player_id"] = and1_zones["player_id"].astype(int)
a1_grouped = and1_zones.groupby(["player_id", "season"])

# ------------------------------------------------------------ player payloads
# Chunked per season: players_by_season[season][player_id] = {games, zones}.
players_by_season: dict[str, dict[str, dict]] = {}

pg_grouped = per_game.groupby(["player_id", "season"])
zn_grouped = zones.groupby(["player_id", "season"])

for (pid, season) in qual_keys:
    entry: dict = {}
    try:
        g = pg_grouped.get_group((pid, season))
        entry["games"] = [
            [int(a), round(float(x), 3), int(n),
             *fg_by_key.get((pid, gid, season), (0.0, 0.0))]
            for a, x, n, gid in zip(g["actual"], g["xfta"], g["poss"], g["game_id"])
        ]
    except KeyError:
        entry["games"] = []
    try:
        z = zn_grouped.get_group((pid, season))
        total = z["n"].sum()
        entry["zones"] = [
            {
                "zone": zr.zone,
                "area": zr.area,
                "n": int(zr.n),
                "share": round(zr.n / total, 4),
            }
            for zr in z.itertuples()
        ]
    except KeyError:
        entry["zones"] = []
    and1, sf2, sf3 = fouls_by_key.get((pid, season), (0, 0, 0))
    try:
        az = a1_grouped.get_group((pid, season))
        located = int(az["n"].sum())
        a1z = [
            {
                "zone": zr.zone,
                "area": zr.area,
                "n": int(zr.n),
                "share": round(zr.n / located, 4),
            }
            for zr in az.itertuples()
        ]
    except KeyError:
        located, a1z = 0, []
    entry["fouls"] = {
        "and1": and1,
        "sf2": sf2,
        "sf3": sf3,
        "located": located,
        "zones": a1z,
    }
    players_by_season.setdefault(season, {})[str(pid)] = entry

# ------------------------------------------------------------- calibration
pred = pd.read_sql(
    """SELECT pr.sfta, pr.xfta, pr.season
       FROM predictions_poss_clean pr
       JOIN possessions p
         ON p.game_id = pr.game_id
        AND p.possession_number = pr.possession_number
       WHERE p.finisher_player_id IS NOT NULL""",
    conn,
)
# Calibration of the FTAOE baseline at the grain it is used: qualified
# player-seasons in deciles of expected FTs per possession (shot diet), against
# actual. `pred` (the context model) still supplies the league rates below.
_cal = lb[lb["possessions"] >= QUALIFY_POSS].assign(
    exp_rate=lambda d: d.xfta_total / d.possessions,
    act_rate=lambda d: d.actual_fta_from_fouls / d.possessions)
_cal["bin"] = pd.qcut(_cal["exp_rate"], 10, duplicates="drop")
cal = (
    _cal.groupby("bin", observed=True)
    .agg(pred_mean=("exp_rate", "mean"), actual_mean=("act_rate", "mean"),
         n=("exp_rate", "size"))
    .reset_index(drop=True)
)
calibration = [
    {
        "pred": round(r.pred_mean, 4),
        "actual": round(r.actual_mean, 4),
        "n": int(r.n),
    }
    for r in cal.itertuples()
]

# ------------------------------------------------------- referees + teams
# Officials over the expected whistle of the games they worked (shot diet plus
# the players on the floor), shrunk to what the data supports: referees.py.
# Officials qualify at 20 games in a season.
#
# Final game script from the last *nonzero* running margin: score_margin is
# only stamped on scoring events (0 elsewhere), so 0 is missing, not tied.
# close <= 5, mid 6-12, blowout 13+. Every game classifies.
ref_poss = pd.read_sql(
    """WITH ls AS (
           SELECT game_id, ABS(score_margin) AS m,
                  ROW_NUMBER() OVER (
                      PARTITION BY game_id
                      ORDER BY period DESC, seconds_remaining_in_period ASC
                  ) AS rn
           FROM shots WHERE score_margin != 0
       ),
       fm AS (
           SELECT game_id,
                  CASE WHEN m <= 5 THEN 'close'
                       WHEN m <= 12 THEN 'mid'
                       ELSE 'blowout' END AS bucket
           FROM ls WHERE rn = 1
       )
       SELECT p.game_id, p.period, p.sfta, g.season, fm.bucket,
              p.finisher_player_id AS pid
       FROM possessions p
       JOIN games g ON g.GAME_ID = p.game_id
       JOIN game_meta m ON m.game_id = p.game_id
       JOIN fm ON fm.game_id = p.game_id""",
    conn,
)
ref_poss["q"] = np.where(
    ref_poss["period"] <= 4,
    "Q" + ref_poss["period"].astype(int).astype(str),
    "OT",
)
ref_diet = pd.read_sql(
    "SELECT game_id, player_id AS pid, xft FROM diet_game", conn)
_meta = pd.read_sql(
    "SELECT game_id, ref1_id, ref1_name, ref2_id, ref2_name, ref3_id, ref3_name "
    "FROM game_meta", conn)
ref_games = pd.concat(
    [_meta[["game_id", f"ref{n}_id", f"ref{n}_name"]]
     .set_axis(["game_id", "ref_id", "ref_name"], axis=1) for n in (1, 2, 3)],
    ignore_index=True,
).dropna(subset=["ref_id"])
ref_games["ref_id"] = ref_games["ref_id"].astype(int)
referees_out, ref_profiles, referees_meta = referees.build(
    ref_poss, ref_diet, ref_games, qualify_games=20)

# Team-season FTAOE drawn (offense) and conceded (defense), anchored
# expectations so each season sums to ~0 on both sides.
tm = pd.read_sql(
    """SELECT p.game_id, p.possession_number, g.season,
              p.offense_team_id, p.sfta, pr.xfta,
              m.home_team_id, m.away_team_id
       FROM possessions p
       JOIN games g ON g.GAME_ID = p.game_id
       JOIN predictions_poss_clean pr
         ON pr.game_id = p.game_id AND pr.possession_number = p.possession_number
       JOIN game_meta m ON m.game_id = p.game_id
       WHERE p.offense_team_id > 0
         AND p.finisher_player_id IS NOT NULL""",
    conn,
)
tm["def_team_id"] = np.where(
    tm["offense_team_id"] == tm["home_team_id"],
    tm["away_team_id"], tm["home_team_id"],
)
def team_side(key):
    agg = (
        tm.groupby([key, "season"])
        .agg(poss=("sfta", "size"), fta=("sfta", "sum"), xfta=("xfta", "sum"))
        .reset_index()
    )
    agg["per100"] = (agg["fta"] - agg["xfta"]) / agg["poss"] * 100
    return agg
off = team_side("offense_team_id")
def_ = team_side("def_team_id")

# Team-level shot-value suite: what the looks a team generated were worth
# (selection) and FG points over expected (making), per 100 offensive
# possessions, centred on the possession-weighted league mean of the season
# so the columns read vs-league like drawn/conceded do. Sourced from
# team_shot_value (written by shot_value.py, same xFG cross-fit as the
# player suite) with the same possession denominator as the FT columns.
_tsv = pd.read_sql(
    "SELECT team_id, season, off_act_fg_pts, off_exp_fg_pts FROM team_shot_value",
    conn,
)
_tsv_by_key = {
    (int(r.team_id), r.season): (float(r.off_exp_fg_pts), float(r.off_act_fg_pts))
    for r in _tsv.itertuples()
}

teams_out = {}
for season in sorted(off["season"].unique()):
    o = off[off["season"] == season].set_index("offense_team_id")
    d = def_[def_["season"] == season].set_index("def_team_id")
    valid = [
        tid for tid in o.index
        if tid in TEAM_ABBREV and tid in d.index and (int(tid), season) in _tsv_by_key
    ]
    lg_poss = sum(int(o.loc[t, "poss"]) for t in valid)
    lg_exp = sum(_tsv_by_key[(int(t), season)][0] for t in valid)
    lg_act = sum(_tsv_by_key[(int(t), season)][1] for t in valid)
    lg_sv100 = lg_exp / lg_poss * 100 if lg_poss else 0.0
    lg_make100 = (lg_act - lg_exp) / lg_poss * 100 if lg_poss else 0.0
    rows = []
    for tid in o.index:
        if tid not in TEAM_ABBREV or tid not in d.index:
            continue
        poss = int(o.loc[tid, "poss"])
        row = {
            "team": TEAM_ABBREV[tid],
            "drawn": round(float(o.loc[tid, "per100"]), 2),
            "conceded": round(float(d.loc[tid, "per100"]), 2),
            "poss": poss,
        }
        tsv = _tsv_by_key.get((int(tid), season))
        if tsv and poss:
            exp_pts, act_pts = tsv
            row["sv100"] = round(exp_pts / poss * 100 - lg_sv100, 2)
            row["make100"] = round((act_pts - exp_pts) / poss * 100 - lg_make100, 2)
        else:
            row["sv100"] = None
            row["make100"] = None
        rows.append(row)
    rows.sort(key=lambda r: -r["drawn"])
    teams_out[season] = rows

# ------------------------------------------------- shot-value suite (xFG%)
# Combined shot value: expected points per shot fusing xFG% (make value) and
# xFTA (foul-drawing value). Present only if shot_value.py has populated the
# table, so the export never hard-depends on the model having run.
shot_value_out: dict[str, list] = {}
has_sv = conn.execute(
    "SELECT name FROM sqlite_master WHERE type='table' AND name='shot_value'"
).fetchone()
if has_sv:
    sv = pd.read_sql(
        """SELECT player_id, player_name, position, season, possessions,
                  fga, fg_pct, xfg_pct, shot_making_oe, xpoints_per_shot,
                  fg_pts_oe_per100, ft_pct, ftaoe, points_oe_per100
           FROM shot_value WHERE possessions >= ?""",
        conn, params=(QUALIFY_POSS,),
    )
    sv["player_id"] = sv["player_id"].astype(int)
    for season, grp in sv.groupby("season"):
        rows = [
            {
                "id": int(r.player_id),
                "name": r.player_name,
                "pos": (r.position or "").split("-")[0] or None,
                "teams": teams_by_key.get((int(r.player_id), season), []),
                "fga": int(r.fga),
                "poss": int(r.possessions),
                "fgPct": round(r.fg_pct * 100, 1),
                "xfgPct": round(r.xfg_pct * 100, 1),
                "makeOE": round(r.shot_making_oe, 1),
                "xptsShot": round(r.xpoints_per_shot, 3),
                "fgPoe100": round(r.fg_pts_oe_per100, 2),
                "ftPct": round(r.ft_pct, 3),
                "ftaoe100": round(r.ftaoe / r.possessions * 100, 1),
                "poe100": round(r.points_oe_per100, 2),
            }
            for r in grp.itertuples()
        ]
        rows.sort(key=lambda x: -x["poe100"])
        shot_value_out[season] = rows

# ------------------------------------------------------------------- meta
metrics = json.loads(
    (Path(ARTIFACT_DIR) / "headline_v4_context_metrics.json").read_text()
)
# The retired context baseline's paper figures, live era only, for the history.
_ART = Path(__file__).parent / "model_artifacts"
n_poss = pred.shape[0]

# Reliability of FTAOE as shipped (shot-diet baseline), computed from the
# per-game series above rather than read from the paper's artifacts, which
# describe the retired context-only baseline.
_halves = []
for (pid, season), g in per_game.groupby(["player_id", "season"]):
    if (pid, season) not in qual_keys or len(g) < 10:
        continue
    odd, even = g.iloc[::2], g.iloc[1::2]
    _halves.append((
        (odd.actual.sum() - odd.xfta.sum()) / odd.poss.sum() * 100,
        (even.actual.sum() - even.xfta.sum()) / even.poss.sum() * 100,
        (odd.poss.sum() + even.poss.sum()) / 2))
_h = pd.DataFrame(_halves, columns=["a", "b", "n"])
_r_half = float(_h.a.corr(_h.b))
_qlb = lb[lb["possessions"] >= QUALIFY_POSS]
_yoy = []
for s1, s2 in zip(sorted(_qlb.season.unique()), sorted(_qlb.season.unique())[1:]):
    a = _qlb[_qlb.season == s1].set_index("player_id")["ftaoe_per_100"]
    b = _qlb[_qlb.season == s2].set_index("player_id")["ftaoe_per_100"]
    common = a.index.intersection(b.index)
    if len(common) > 2:
        _yoy.append({"pair": f"{s1} to {s2}",
                     "r": round(float(a[common].corr(b[common])), 3),
                     "n": int(len(common))})
reliability = {
    "fullSeasonR": round(2 * _r_half / (1 + _r_half), 3),
    "yoyMeanR": round(float(np.mean([p["r"] for p in _yoy])), 3),
    "yoyPairs": _yoy,
    # possessions at which the season rate is half signal: n_half (1 - r) / r
    "paddingK": int(round(_h.n.mean() * (1 - _r_half) / _r_half)),
}
all_seasons = sorted(lb["season"].unique().tolist())
# The site's default season: latest with >= 50 qualified players, so a
# brand-new October season stays selectable but does not take over the
# landing/leaderboard until per-100 rates mean something.
qual_counts = (
    lb[lb["possessions"] >= QUALIFY_POSS].groupby("season").size().to_dict()
)
# What the shot-diet baseline does and does not take out, measured on the
# qualified rows as shipped. The retired context baseline's figures (raw-rate
# r 0.995, height r 0.39) come from the paper's artifacts, for the history.
_vrb = json.loads((_ART / "variant_raw_baseline.json").read_text())
_avl = json.loads((_ART / "variant_archetype_vs_linear.json").read_text())
_heights = pd.read_sql(
    "SELECT player_id, season, height_inches FROM player_season", conn)
_heights["player_id"] = _heights["player_id"].astype(int)
_cq = _qlb.merge(_heights, on=["player_id", "season"], how="left")
_cq["raw100"] = _cq["actual_fta_from_fouls"] / _cq["possessions"] * 100
_confounds = {
    "rawRateCorr": round(float(_cq.ftaoe_per_100.corr(_cq.raw100)), 3),
    "heightCorr": round(float(_cq.ftaoe_per_100.corr(_cq.height_inches)), 3),
    "rawHeightCorr": round(float(_cq.raw100.corr(_cq.height_inches)), 3),
    # null for an era with no tracking seasons (the archive before 2013-14)
    "trackingCorr": (None if pd.isna(_cq.ftaoe_per_100.corr(_cq.sadj_per100))
                     else round(float(_cq.ftaoe_per_100.corr(_cq.sadj_per100)), 3)),
    "contextRawRateCorr": _vrb["agreement"]["pearsonR"],
    "contextHeightCorr": _avl["heightGradient"]["headline"],
}
# League free throws per attempt by zone, the expectation's building blocks.
_rates = pd.read_sql("SELECT season, zone, rate FROM diet_rates", conn)
diet_rates = {
    season: {r.zone: round(float(r.rate), 3) for r in grp.itertuples()}
    for season, grp in _rates.groupby("season")
}

default_season = next(
    (s2 for s2 in reversed(all_seasons) if qual_counts.get(s2, 0) >= 50),
    all_seasons[-1],
)
meta = {
    "seasons": all_seasons,
    "defaultSeason": default_season,
    "qualifyPossessions": QUALIFY_POSS,
    "nPossessions": int(n_poss),
    "leagueRatePer100": round(float(pred["sfta"].mean()) * 100, 2),
    "leagueRateBySeason": {
        season: round(float(grp["sfta"].mean()) * 100, 2)
        for season, grp in pred.groupby("season")
    },
    "modelLiftPct": round(metrics["oof_lift_pct"], 2),
    "foldLifts": [
        {"season": f["season"], "liftPct": round(f["lift_pct"], 2)}
        for f in metrics["folds"]
    ],
    "reliability": {
        "fullSeasonR": reliability["fullSeasonR"],
        "yoyMeanR": reliability["yoyMeanR"],
        "yoyPairs": reliability["yoyPairs"],
        "paddingK": reliability["paddingK"],
    },
    "confounds": _confounds,
    "dietRates": diet_rates,
    "referees": referees_meta,
}

out = {
    "meta": meta,
    "leaderboard": leaderboard,
    "distributions": distributions,
    "leagueZones": league_zone_out,
    "calibration": calibration,
    "referees": referees_out,
    "refProfiles": ref_profiles,
    "teams": teams_out,
    "shotValue": shot_value_out,
}

OUT.parent.mkdir(parents=True, exist_ok=True)
# Remove stale chunks from previous exports before writing.
for old in OUT.parent.glob("players-*.json"):
    old.unlink()
OUT.write_text(json.dumps(out, separators=(",", ":")))
size_mb = OUT.stat().st_size / 1e6
print(f"Wrote {OUT} ({size_mb:.2f} MB core)")
n_pages = 0
for season, payload in sorted(players_by_season.items()):
    chunk = OUT.parent / f"players-{season}.json"
    chunk.write_text(json.dumps(payload, separators=(",", ":")))
    n_pages += len(payload)
    print(f"  {chunk.name}: {len(payload)} players "
          f"({chunk.stat().st_size / 1e6:.2f} MB)")
print(f"  leaderboard rows: {len(leaderboard)}")
print(f"  player-season pages: {n_pages}")
print(f"  league rate/100:  {meta['leagueRatePer100']}")
