"""Does the model earn its keep? FTAOE against the raw rate it replaces.

The paper reports FTAOE's season-level reliability but never compares it to the
statistic FTAOE claims to improve on: shooting-foul free throws per 100
possessions, with no model at all. That comparison is the obvious challenge, and
it cuts both ways:

  - If the raw rate is just as reliable AND ranks players nearly identically,
    the model adds nothing and FTAOE is free-throw rate with extra steps.
  - If FTAOE ranks players differently from the raw rate, the model is doing
    real work, and the reliability figure is a property of the residual rather
    than of the underlying rate.

Reliability alone cannot settle this. A raw rate will normally be MORE reliable
than a residual, because subtracting a noisy expectation adds variance. So the
decisive quantity is rank divergence: how much does adjusting for context
actually move players?

Reports, for raw rate and FTAOE alike:
  split-half r, Spearman-Brown full-season r, padding K, year-over-year r,
  the rank correlation between the two metrics, and the players they most
  disagree about.

Writes model_artifacts/variant_raw_baseline.json.
"""
from __future__ import annotations

import json
import os
import sqlite3

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from config import DB_PATH, SEASONS

MODEL_DIR = "model_artifacts"
QUALIFY = 300


def load_per_game() -> pd.DataFrame:
    conn = sqlite3.connect(DB_PATH)
    pg = pd.read_sql(
        """SELECT p.finisher_player_id AS player_id, g.season, p.game_id,
                  SUM(p.sfta) AS a, SUM(pr.xfta) AS x, COUNT(*) AS n
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
    names = pd.read_sql(
        "SELECT player_id, season, player_name FROM player_season", conn
    )
    conn.close()
    pg["player_id"] = pg["player_id"].astype(int)
    return pg, names


def split_half(pg: pd.DataFrame, kind: str) -> dict:
    """kind='raw' -> a/n*100 ; kind='ftaoe' -> (a-x)/n*100."""
    pg = pg.sort_values(["player_id", "season", "game_id"]).copy()
    pg["gidx"] = pg.groupby(["player_id", "season"]).cumcount()
    pg["half"] = pg["gidx"] % 2
    h = (pg.groupby(["player_id", "season", "half"])[["a", "x", "n"]]
         .sum().reset_index())
    w = h.pivot(index=["player_id", "season"], columns="half",
                values=["a", "x", "n"])
    w.columns = [f"{v}{k}" for v, k in w.columns]
    w = w.dropna().join(
        pg.groupby(["player_id", "season"])["n"].sum().rename("poss")
    )
    q = w[w["poss"] >= QUALIFY].copy()
    if kind == "raw":
        q["h0"] = q["a0"] / q["n0"] * 100
        q["h1"] = q["a1"] / q["n1"] * 100
    else:
        q["h0"] = (q["a0"] - q["x0"]) / q["n0"] * 100
        q["h1"] = (q["a1"] - q["x1"]) / q["n1"] * 100
    r = float(np.corrcoef(q["h0"], q["h1"])[0, 1])
    r_full = 2 * r / (1 + r)
    n_half = float((q["n0"].mean() + q["n1"].mean()) / 2)
    return {
        "splitHalfR": round(r, 4),
        "fullSeasonR": round(r_full, 4),
        "paddingK": round(n_half * (1 - r) / r),
        "nPlayerSeasons": int(len(q)),
    }


def season_table(pg: pd.DataFrame, names: pd.DataFrame) -> pd.DataFrame:
    ps = (pg.groupby(["player_id", "season"])[["a", "x", "n"]]
          .sum().reset_index())
    ps = ps[ps["n"] >= QUALIFY].copy()
    ps["raw_per100"] = ps["a"] / ps["n"] * 100
    ps["ftaoe_per100"] = (ps["a"] - ps["x"]) / ps["n"] * 100
    return ps.merge(names, on=["player_id", "season"], how="left")


def yoy(ps: pd.DataFrame, col: str) -> dict:
    rs = []
    for s1, s2 in zip(SEASONS[:-1], SEASONS[1:]):
        a = ps[ps["season"] == s1].set_index("player_id")[col]
        b = ps[ps["season"] == s2].set_index("player_id")[col]
        common = a.index.intersection(b.index)
        if len(common) < 30:
            continue
        rs.append(float(np.corrcoef(a.loc[common], b.loc[common])[0, 1]))
    return {"meanR": round(float(np.mean(rs)), 4),
            "perPair": [round(r, 3) for r in rs]}


def main() -> None:
    pg, names = load_per_game()
    ps = season_table(pg, names)

    rel_raw = split_half(pg, "raw")
    rel_oe = split_half(pg, "ftaoe")
    yoy_raw = yoy(ps, "raw_per100")
    yoy_oe = yoy(ps, "ftaoe_per100")

    rho, p = spearmanr(ps["raw_per100"], ps["ftaoe_per100"])
    pear = float(np.corrcoef(ps["raw_per100"], ps["ftaoe_per100"])[0, 1])

    # Rank divergence: where does adjusting for context actually move a player?
    ps = ps.copy()
    ps["rank_raw"] = ps.groupby("season")["raw_per100"].rank(
        ascending=False, method="min")
    ps["rank_oe"] = ps.groupby("season")["ftaoe_per100"].rank(
        ascending=False, method="min")
    ps["rank_shift"] = (ps["rank_raw"] - ps["rank_oe"]).abs()

    def top_ov(k):
        A = set(ps.nlargest(k, "raw_per100").index)
        B = set(ps.nlargest(k, "ftaoe_per100").index)
        return len(A & B)

    movers = ps.reindex(
        (ps["rank_raw"] - ps["rank_oe"]).abs().sort_values(ascending=False).index
    ).head(10)

    print(f"qualified player-seasons: {len(ps):,}\n")
    print(f"{'':22s} {'split-half':>11s} {'full-season':>12s} {'K':>5s} {'YoY':>7s}")
    print(f"{'raw SF FT/100':22s} {rel_raw['splitHalfR']:>11.3f} "
          f"{rel_raw['fullSeasonR']:>12.3f} {rel_raw['paddingK']:>5d} "
          f"{yoy_raw['meanR']:>7.3f}")
    print(f"{'FTAOE/100':22s} {rel_oe['splitHalfR']:>11.3f} "
          f"{rel_oe['fullSeasonR']:>12.3f} {rel_oe['paddingK']:>5d} "
          f"{yoy_oe['meanR']:>7.3f}")

    print(f"\nagreement between the two metrics:")
    print(f"  Spearman rho = {rho:.4f}   Pearson r = {pear:.4f}")
    print(f"  top-10 overlap {top_ov(10)}/10, top-25 {top_ov(25)}/25, "
          f"top-50 {top_ov(50)}/50")
    print(f"  within-season rank shift: mean {ps['rank_shift'].mean():.1f}, "
          f"p95 {ps['rank_shift'].quantile(0.95):.0f}, "
          f"max {ps['rank_shift'].max():.0f}")
    print("\nplayers the context adjustment moves most:")
    for r in movers.itertuples():
        print(f"  {r.player_name:26s} {r.season}  raw {r.raw_per100:6.2f} "
              f"(rank {int(r.rank_raw):3d}) -> FTAOE {r.ftaoe_per100:+6.2f} "
              f"(rank {int(r.rank_oe):3d})")

    out = {
        "qualifyPossessions": QUALIFY,
        "nPlayerSeasons": int(len(ps)),
        "rawRate": {**rel_raw, "yoy": yoy_raw},
        "ftaoe": {**rel_oe, "yoy": yoy_oe},
        "agreement": {
            "spearmanRho": round(float(rho), 4),
            "spearmanP": float(p),
            "pearsonR": round(pear, 4),
            "top10Overlap": top_ov(10),
            "top25Overlap": top_ov(25),
            "top50Overlap": top_ov(50),
            "rankShiftMean": round(float(ps["rank_shift"].mean()), 2),
            "rankShiftP95": float(ps["rank_shift"].quantile(0.95)),
            "rankShiftMax": float(ps["rank_shift"].max()),
        },
        "biggestMovers": [
            {"player": r.player_name, "season": r.season,
             "rawPer100": round(float(r.raw_per100), 3),
             "rawRank": int(r.rank_raw),
             "ftaoePer100": round(float(r.ftaoe_per100), 3),
             "ftaoeRank": int(r.rank_oe)}
            for r in movers.itertuples()
        ],
    }
    path = os.path.join(MODEL_DIR, "variant_raw_baseline.json")
    with open(path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"\nwrote {path}")


if __name__ == "__main__":
    main()
