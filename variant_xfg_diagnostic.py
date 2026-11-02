"""The same diagnostic, run on the shooting side.

The foul-drawing analysis concluded that FTAOE is the raw rate with extra steps:
the fitted expectation carried 0.9% of between-player variance and the residual
correlated 0.995 with the unadjusted rate. That conclusion is only interesting
if the diagnostic can also come out the other way, on a metric built the same
way by the same pipeline. Otherwise it is a statement about our code rather than
about residual metrics.

So this runs the identical test on shot-making. Expected field-goal points per
attempt varies enormously across players, because a corner-three specialist and
a rim finisher take completely different shots, whereas expected shooting-foul
rate barely varies at all. If the diagnostic is measuring what it claims to,
shot-making should pass where foul-drawing failed.

Reported at qualified player-season grain, exactly as for FTAOE:
  raw       actual field-goal points per 100 attempts
  expected  xFG points per 100 attempts (the thing being subtracted)
  oe        actual - expected, i.e. shot-making over expected

  1. Var(expected) / Var(raw)                 -- can the subtraction reorder?
  2. corr(oe, raw)                            -- is the residual a new ordering?
  3. split-half / Spearman-Brown / YoY of both
  4. correlation with finisher height          -- the confound that survived FTAOE

Writes model_artifacts/variant_xfg_diagnostic.json.
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
QUALIFY_FGA = 300
SEED = 42
N_BOOT = 2000


def load():
    conn = sqlite3.connect(DB_PATH)
    pg = pd.read_sql(
        """SELECT player_id, season, game_id, fga, act_fg_pts, exp_fg_pts
           FROM player_game_shot_value WHERE fga > 0 ORDER BY game_id""",
        conn,
    )
    ps = pd.read_sql(
        """SELECT player_id, season, player_name, position, fga,
                  act_fg_pts, exp_fg_pts FROM shot_value""",
        conn,
    )
    ht = pd.read_sql(
        "SELECT player_id, season, height_inches FROM player_season", conn
    )
    conn.close()
    ps = ps[ps["fga"] >= QUALIFY_FGA].merge(ht, on=["player_id", "season"],
                                            how="left")
    ps["raw"] = ps["act_fg_pts"] / ps["fga"] * 100
    ps["expected"] = ps["exp_fg_pts"] / ps["fga"] * 100
    ps["oe"] = ps["raw"] - ps["expected"]
    return pg, ps


def split_half(pg: pd.DataFrame, qualified: set, kind: str) -> dict:
    pg = pg.sort_values(["player_id", "season", "game_id"]).copy()
    pg["gidx"] = pg.groupby(["player_id", "season"]).cumcount()
    pg["half"] = pg["gidx"] % 2
    h = (pg.groupby(["player_id", "season", "half"])
         [["fga", "act_fg_pts", "exp_fg_pts"]].sum().reset_index())
    w = h.pivot(index=["player_id", "season"], columns="half",
                values=["fga", "act_fg_pts", "exp_fg_pts"])
    w.columns = [f"{v}{k}" for v, k in w.columns]
    w = w.dropna()
    w = w[[i in qualified for i in w.index]]
    w = w[(w["fga0"] > 0) & (w["fga1"] > 0)]
    for j in (0, 1):
        raw = w[f"act_fg_pts{j}"] / w[f"fga{j}"] * 100
        exp = w[f"exp_fg_pts{j}"] / w[f"fga{j}"] * 100
        w[f"v{j}"] = raw if kind == "raw" else raw - exp
    r = float(np.corrcoef(w["v0"], w["v1"])[0, 1])
    n_half = float((w["fga0"].mean() + w["fga1"].mean()) / 2)
    return {"splitHalfR": round(r, 4),
            "fullSeasonR": round(2 * r / (1 + r), 4),
            "paddingK": round(n_half * (1 - r) / r),
            "meanHalfFga": round(n_half),
            "nPlayerSeasons": int(len(w))}


def yoy(ps: pd.DataFrame, col: str) -> dict:
    rs = []
    for s1, s2 in zip(SEASONS[:-1], SEASONS[1:]):
        a = ps[ps.season == s1].set_index("player_id")[col]
        b = ps[ps.season == s2].set_index("player_id")[col]
        common = a.index.intersection(b.index)
        if len(common) >= 30:
            rs.append(float(np.corrcoef(a.loc[common], b.loc[common])[0, 1]))
    return {"meanR": round(float(np.mean(rs)), 4),
            "perPair": [round(x, 3) for x in rs]}


def boot_ci(df, a, b):
    rng = np.random.RandomState(SEED)
    players = df["player_id"].unique()
    idx = {p: df.index[df["player_id"] == p].to_numpy() for p in players}
    out = []
    for _ in range(N_BOOT):
        pick = rng.choice(players, size=len(players), replace=True)
        s = df.loc[np.concatenate([idx[p] for p in pick])]
        out.append(np.corrcoef(s[a], s[b])[0, 1])
    lo, hi = np.percentile(out, [2.5, 97.5])
    return round(float(lo), 4), round(float(hi), 4)


def main() -> None:
    pg, ps = load()
    ps = ps.reset_index(drop=True)
    qualified = set(zip(ps["player_id"], ps["season"]))
    print(f"qualified player-seasons: {len(ps):,} "
          f"(>= {QUALIFY_FGA} FGA, {ps.player_id.nunique()} players)\n")

    var_share = float(ps["expected"].var() / ps["raw"].var())
    rho, _ = spearmanr(ps["oe"], ps["raw"])
    pear = float(np.corrcoef(ps["oe"], ps["raw"])[0, 1])
    lo, hi = boot_ci(ps, "oe", "raw")

    print("=== 1. can the subtraction reorder anyone? ===")
    print(f"  sd(raw)      {ps['raw'].std():6.2f} pts/100 FGA")
    print(f"  sd(expected) {ps['expected'].std():6.2f}")
    print(f"  Var(expected)/Var(raw) = {var_share:.4f}   "
          f"(foul-drawing: 0.0093)")
    print("\n=== 2. is the residual a new ordering? ===")
    print(f"  corr(shot-making OE, raw pts/100) = {pear:+.4f} "
          f"[{lo:+.4f}, {hi:+.4f}]   Spearman {rho:+.4f}")
    print(f"  (foul-drawing: +0.9953)")

    rel_raw = split_half(pg, qualified, "raw")
    rel_oe = split_half(pg, qualified, "oe")
    y_raw, y_oe = yoy(ps, "raw"), yoy(ps, "oe")
    print("\n=== 3. reliability ===")
    print(f"  {'':10s} {'split-half':>11s} {'full-season':>12s} {'K(FGA)':>8s} {'YoY':>7s}")
    print(f"  {'raw':10s} {rel_raw['splitHalfR']:>11.3f} "
          f"{rel_raw['fullSeasonR']:>12.3f} {rel_raw['paddingK']:>8d} "
          f"{y_raw['meanR']:>7.3f}")
    print(f"  {'OE':10s} {rel_oe['splitHalfR']:>11.3f} "
          f"{rel_oe['fullSeasonR']:>12.3f} {rel_oe['paddingK']:>8d} "
          f"{y_oe['meanR']:>7.3f}")

    hp = ps.dropna(subset=["height_inches"])
    h_raw = float(hp["raw"].corr(hp["height_inches"]))
    h_oe = float(hp["oe"].corr(hp["height_inches"]))
    h_exp = float(hp["expected"].corr(hp["height_inches"]))
    print("\n=== 4. the confound that survived on the foul side ===")
    print(f"  corr(raw, height)      {h_raw:+.4f}")
    print(f"  corr(expected, height) {h_exp:+.4f}")
    print(f"  corr(OE, height)       {h_oe:+.4f}   (FTAOE: +0.3913)")

    verdict = ("shot-making PASSES the diagnostic that foul-drawing failed"
               if abs(pear) < 0.9 and var_share > 0.1 else
               "shot-making fails the same way foul-drawing did")
    print(f"\nVERDICT: {verdict}")

    out = {
        "qualifyFga": QUALIFY_FGA,
        "nPlayerSeasons": int(len(ps)),
        "nPlayers": int(ps.player_id.nunique()),
        "sdRawPer100": round(float(ps["raw"].std()), 3),
        "sdExpectedPer100": round(float(ps["expected"].std()), 3),
        "varianceShare": round(var_share, 4),
        "oeVsRaw": {"pearson": round(pear, 4), "pearsonCI": [lo, hi],
                    "spearman": round(float(rho), 4)},
        "reliability": {"raw": rel_raw, "oe": rel_oe,
                        "rawYoy": y_raw, "oeYoy": y_oe},
        "heightGradient": {"raw": round(h_raw, 4),
                           "expected": round(h_exp, 4),
                           "oe": round(h_oe, 4)},
        "verdict": verdict,
        "comparisonToFoulDrawing": {
            "varianceShare": 0.0093, "oeVsRawPearson": 0.9953,
            "heightGradient": 0.3913,
        },
    }
    path = os.path.join(MODEL_DIR, "variant_xfg_diagnostic.json")
    with open(path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"\nwrote {path}")


if __name__ == "__main__":
    main()
