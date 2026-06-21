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

from config import DB_PATH

QUALIFY_POSS = 300  # threshold for percentile + player pages
OUT = Path(__file__).parent / "site" / "public" / "data.json"

# Static stats.nba.com franchise id -> abbreviation. Public constants, not data.
TEAM_ABBREV = {
    1610612737: "ATL", 1610612738: "BOS", 1610612739: "CLE", 1610612740: "NOP",
    1610612741: "CHI", 1610612742: "DAL", 1610612743: "DEN", 1610612744: "GSW",
    1610612745: "HOU", 1610612746: "LAC", 1610612747: "LAL", 1610612748: "MIA",
    1610612749: "MIL", 1610612750: "MIN", 1610612751: "BKN", 1610612752: "NYK",
    1610612753: "ORL", 1610612754: "IND", 1610612755: "PHI", 1610612756: "PHX",
    1610612757: "POR", 1610612758: "SAC", 1610612759: "SAS", 1610612760: "OKC",
    1610612761: "TOR", 1610612762: "UTA", 1610612763: "MEM", 1610612764: "WAS",
    1610612765: "DET", 1610612766: "CHA",
}

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
              SUM(p.sfta) AS actual, SUM(pr.xfta) AS xfta,
              COUNT(*) AS poss
       FROM possessions p
       JOIN games g ON g.GAME_ID = p.game_id
       JOIN predictions_poss_clean pr
         ON pr.game_id = p.game_id
        AND pr.possession_number = p.possession_number
       WHERE p.finisher_player_id IS NOT NULL
       GROUP BY p.finisher_player_id, g.season, p.game_id
       ORDER BY p.game_id""",
    conn,
)
per_game["player_id"] = per_game["player_id"].astype(int)

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
pred["bin"] = pd.qcut(pred["xfta"], 10, duplicates="drop")
cal = (
    pred.groupby("bin", observed=True)
    .agg(pred_mean=("xfta", "mean"), actual_mean=("sfta", "mean"),
         n=("sfta", "size"))
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
# Per-official rates (descriptive, league-level: each official's games see
# X shooting-foul FTA per 100 possessions). The model already adjusts for
# crew tendency; these tables just show it. Two products:
#   referees   -> per-season index strip (name, games, rate vs league)
#   refProfiles-> per-official profile: headline + how the whistle moves by
#                 quarter and by game script (blowout vs close).
QUALIFY_REF_GAMES = 20
QUARTER_ORDER = ["Q1", "Q2", "Q3", "Q4", "OT"]
SCRIPT_ORDER = ["close", "mid", "blowout"]

# Final game script from the last *nonzero* running margin: score_margin is
# only stamped on scoring events (0 elsewhere), so 0 is missing, not tied.
# close <= 5, mid 6-12, blowout 13+. Every game classifies.
ref_base = pd.read_sql(
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
              m.ref1_id, m.ref1_name, m.ref2_id, m.ref2_name,
              m.ref3_id, m.ref3_name
       FROM possessions p
       JOIN games g ON g.GAME_ID = p.game_id
       JOIN game_meta m ON m.game_id = p.game_id
       JOIN fm ON fm.game_id = p.game_id""",
    conn,
)
ref_base["q"] = np.where(
    ref_base["period"] <= 4,
    "Q" + ref_base["period"].astype(int).astype(str),
    "OT",
)

# League baselines over all possessions (per 100), matching the index strip.
lg_season = ref_base.groupby("season")["sfta"].mean() * 100
lg_quarter = ref_base.groupby(["season", "q"])["sfta"].mean() * 100
lg_script = ref_base.groupby(["season", "bucket"])["sfta"].mean() * 100

# Melt the three official slots to one row per (possession, official).
ref_parts = []
for n in (1, 2, 3):
    sub = ref_base[["game_id", "season", "q", "bucket", "sfta"]].copy()
    sub["ref_id"] = ref_base[f"ref{n}_id"]
    sub["ref_name"] = ref_base[f"ref{n}_name"]
    ref_parts.append(sub[sub["ref_id"].notna()])
refl = pd.concat(ref_parts, ignore_index=True)
refl["ref_id"] = refl["ref_id"].astype(int)
ref_name = refl.groupby("ref_id")["ref_name"].agg(lambda s: s.mode().iat[0])

head = (
    refl.groupby(["ref_id", "season"])
    .agg(games=("game_id", "nunique"), poss=("sfta", "size"), fta=("sfta", "sum"))
    .reset_index()
)
head["per100"] = head["fta"] / head["poss"] * 100
qg = (
    refl.groupby(["ref_id", "season", "q"])
    .agg(poss=("sfta", "size"), fta=("sfta", "sum")).reset_index()
)
qg["per100"] = qg["fta"] / qg["poss"] * 100
sg = (
    refl.groupby(["ref_id", "season", "bucket"])
    .agg(games=("game_id", "nunique"), poss=("sfta", "size"), fta=("sfta", "sum"))
    .reset_index()
)
sg["per100"] = sg["fta"] / sg["poss"] * 100

# Per-season index strip: officials with >= 20 games, sorted by rate vs league.
referees_out = {}
for season, grp in head.groupby("season"):
    rows = []
    for r in grp.itertuples():
        if r.games < QUALIFY_REF_GAMES:
            continue
        lg = float(lg_season[season])
        rows.append({
            "id": int(r.ref_id),
            "name": ref_name[int(r.ref_id)],
            "games": int(r.games),
            "per100": round(r.per100, 2),
            "diff": round(r.per100 - lg, 2),
        })
    rows.sort(key=lambda x: -x["diff"])
    referees_out[season] = rows

# Per-official profile, keyed by id. Each qualified season carries the
# headline plus the by-quarter and by-script splits, each against that
# split's own league baseline (so a Q4 rate is judged vs the league's Q4).
qg_g = qg.groupby(["ref_id", "season"])
sg_g = sg.groupby(["ref_id", "season"])
ref_profiles: dict[str, dict] = {}
for r in head.itertuples():
    if r.games < QUALIFY_REF_GAMES:
        continue
    rid, season = int(r.ref_id), r.season
    prof = ref_profiles.setdefault(
        str(rid), {"name": ref_name[rid], "seasons": [], "detail": {}}
    )
    prof["seasons"].append(season)
    qmap = {qr.q: qr for qr in qg_g.get_group((rid, season)).itertuples()}
    quarters = [
        {
            "q": q,
            "poss": int(qmap[q].poss),
            "per100": round(qmap[q].per100, 2),
            "lg": round(float(lg_quarter[(season, q)]), 2),
        }
        for q in QUARTER_ORDER if q in qmap
    ]
    smap = {sr.bucket: sr for sr in sg_g.get_group((rid, season)).itertuples()}
    script = [
        {
            "b": b,
            "games": int(smap[b].games),
            "poss": int(smap[b].poss),
            "per100": round(smap[b].per100, 2),
            "lg": round(float(lg_script[(season, b)]), 2),
        }
        for b in SCRIPT_ORDER if b in smap
    ]
    prof["detail"][season] = {
        "games": int(r.games),
        "poss": int(r.poss),
        "fta": int(r.fta),
        "per100": round(r.per100, 2),
        "lg": round(float(lg_season[season]), 2),
        "quarters": quarters,
        "script": script,
    }
for prof in ref_profiles.values():
    prof["seasons"] = sorted(prof["seasons"])

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

teams_out = {}
for season in sorted(off["season"].unique()):
    o = off[off["season"] == season].set_index("offense_team_id")
    d = def_[def_["season"] == season].set_index("def_team_id")
    rows = []
    for tid in o.index:
        if tid not in TEAM_ABBREV or tid not in d.index:
            continue
        rows.append({
            "team": TEAM_ABBREV[tid],
            "drawn": round(float(o.loc[tid, "per100"]), 2),
            "conceded": round(float(d.loc[tid, "per100"]), 2),
            "poss": int(o.loc[tid, "poss"]),
        })
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
    (Path(__file__).parent / "model_artifacts" / "headline_v4_context_metrics.json")
    .read_text()
)
reliability = json.loads(
    (Path(__file__).parent / "model_artifacts" / "reliability.json").read_text()
)
n_poss = pred.shape[0]
all_seasons = sorted(lb["season"].unique().tolist())
# The site's default season: latest with >= 50 qualified players, so a
# brand-new October season stays selectable but does not take over the
# landing/leaderboard until per-100 rates mean something.
qual_counts = (
    lb[lb["possessions"] >= QUALIFY_POSS].groupby("season").size().to_dict()
)
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
