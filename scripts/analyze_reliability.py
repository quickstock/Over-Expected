"""Reliability of FTAOE per 100: is it a skill, and how fast does it
stabilize?

Three measurements, written to model_artifacts/reliability.json:

1. Split-half reliability: within each qualified player-season, split
   games into odd/even halves, compute FTAOE/100 in each half from the
   anchored expectations, correlate across players. Spearman-Brown
   doubles it to a full-season figure.
2. Padding constant K (Tango method): K = n_half * (1 - r_half) / r_half.
   Padding a player's FTAOE denominator with K league-average possessions
   gives a shrunken estimate: stabilized per100 = ftaoe / (poss + K) * 100
   (padded possessions contribute actual == expected, so only the
   denominator grows).
3. Year-over-year reliability: corr of FTAOE/100 across consecutive
   seasons for players qualified (>= 300 finisher-possessions) in both.

All inputs are the same leak-free tables the site ships.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
from config import DB_PATH, SEASONS  # noqa: E402

QUALIFY = 300

conn = sqlite3.connect(DB_PATH)

# Per-game actual/expected/poss per player-season (same join as the export).
pg = pd.read_sql(
    """SELECT p.finisher_player_id AS player_id, g.season, p.game_id,
              SUM(p.sfta) AS a, SUM(pr.xfta) AS x, COUNT(*) AS n
       FROM possessions p
       JOIN games g ON g.GAME_ID = p.game_id
       JOIN predictions_poss_clean pr
         ON pr.game_id = p.game_id AND pr.possession_number = p.possession_number
       WHERE p.finisher_player_id IS NOT NULL
       GROUP BY p.finisher_player_id, g.season, p.game_id
       ORDER BY p.game_id""",
    conn,
)
pg["player_id"] = pg["player_id"].astype(int)

# ---------------------------------------------------------- split-half
pg["gidx"] = pg.groupby(["player_id", "season"]).cumcount()
pg["half"] = pg["gidx"] % 2
halves = (
    pg.groupby(["player_id", "season", "half"])[["a", "x", "n"]]
    .sum()
    .reset_index()
)
wide = halves.pivot(index=["player_id", "season"], columns="half",
                    values=["a", "x", "n"])
wide.columns = [f"{v}{h}" for v, h in wide.columns]
wide = wide.dropna()
totals = pg.groupby(["player_id", "season"])["n"].sum().rename("poss")
wide = wide.join(totals)
q = wide[wide["poss"] >= QUALIFY].copy()
q["r0"] = (q["a0"] - q["x0"]) / q["n0"] * 100
q["r1"] = (q["a1"] - q["x1"]) / q["n1"] * 100
r_half = float(np.corrcoef(q["r0"], q["r1"])[0, 1])
r_full = 2 * r_half / (1 + r_half)  # Spearman-Brown
n_half = float((q["n0"].mean() + q["n1"].mean()) / 2)
k_pad = n_half * (1 - r_half) / r_half

print(f"split-half (odd/even games), {len(q)} qualified player-seasons:")
print(f"  r_half = {r_half:.3f}  -> full-season (Spearman-Brown) r = {r_full:.3f}")
print(f"  mean half size = {n_half:.0f} poss -> padding K = {k_pad:.0f} possessions")
print(f"  implied reliability at 300 poss: {300 / (300 + k_pad):.2f}; "
      f"at 1000: {1000 / (1000 + k_pad):.2f}")

# ---------------------------------------------------------- year over year
lb = pd.read_sql(
    """SELECT player_id, season, possessions, ftaoe_per_100
       FROM player_season_xfta_poss_lb_clean WHERE possessions >= ?""",
    conn,
    params=(QUALIFY,),
)
lb["player_id"] = lb["player_id"].astype(int)
pairs = []
pair_details = []
for s1, s2 in zip(SEASONS[:-1], SEASONS[1:]):
    a = lb[lb["season"] == s1].set_index("player_id")["ftaoe_per_100"]
    b = lb[lb["season"] == s2].set_index("player_id")["ftaoe_per_100"]
    common = a.index.intersection(b.index)
    r = float(np.corrcoef(a.loc[common], b.loc[common])[0, 1])
    pairs.append(r)
    pair_details.append({"pair": f"{s1} to {s2}", "r": round(r, 3),
                         "n": int(len(common))})
    print(f"YoY {s1} -> {s2}: r = {r:.3f} (n = {len(common)})")
yoy_mean = float(np.mean(pairs))
print(f"YoY mean r = {yoy_mean:.3f}")

# Context: YoY of raw possessions count (role stability) for comparison.
out = {
    "splitHalfR": round(r_half, 3),
    "fullSeasonR": round(r_full, 3),
    "meanHalfPoss": round(n_half),
    "paddingK": round(k_pad),
    "yoyMeanR": round(yoy_mean, 3),
    "yoyPairs": pair_details,
    "qualify": QUALIFY,
    "nPlayerSeasons": int(len(q)),
}
path = ROOT / "model_artifacts" / "reliability.json"
path.write_text(json.dumps(out, indent=2))
print(f"\nwrote {path}")
