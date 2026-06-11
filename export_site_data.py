"""Export the leak-free xFTA tables into one static JSON for the website.

Sources (all clean / leak-free):
  - player_season_xfta_poss_lb_clean  -> leaderboard
  - possessions + predictions_poss_clean + games -> per-player per-game
    cumulative actual vs baseline series (game index order = game_id order)
  - training_fga + shots -> charged-FGA shot zones per player-season
  - predictions_poss_clean -> league distribution inputs + calibration bins

Output: site/public/data.json (single file the frontend ships with).
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
              SUM(p.sfta) AS actual, SUM(pr.xfta) AS xfta
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

# ------------------------------------------------------------ player payloads
players = {}
for r in lb[lb["possessions"] >= QUALIFY_POSS].itertuples():
    pid, season = int(r.player_id), r.season
    players.setdefault(pid, {"name": r.player_name, "seasons": {}})

pg_grouped = per_game.groupby(["player_id", "season"])
zn_grouped = zones.groupby(["player_id", "season"])

for (pid, season) in qual_keys:
    entry = players[pid]["seasons"].setdefault(season, {})
    try:
        g = pg_grouped.get_group((pid, season))
        entry["games"] = [
            [int(a), round(float(x), 3)]
            for a, x in zip(g["actual"], g["xfta"])
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

# ------------------------------------------------------------- calibration
pred = pd.read_sql(
    "SELECT sfta, xfta, season FROM predictions_poss_clean", conn
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

# ------------------------------------------------------------------- meta
metrics = json.loads(
    (Path(__file__).parent / "model_artifacts" / "headline_v3_clean_metrics.json")
    .read_text()
)
n_poss = pred.shape[0]
meta = {
    "seasons": sorted(lb["season"].unique().tolist()),
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
}

out = {
    "meta": meta,
    "leaderboard": leaderboard,
    "distributions": distributions,
    "leagueZones": league_zone_out,
    "players": {str(k): v for k, v in players.items()},
    "calibration": calibration,
}

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(out, separators=(",", ":")))
size_mb = OUT.stat().st_size / 1e6
print(f"Wrote {OUT} ({size_mb:.2f} MB)")
print(f"  leaderboard rows: {len(leaderboard)}")
print(f"  player pages:     {len(players)}")
print(f"  league rate/100:  {meta['leagueRatePer100']}")
