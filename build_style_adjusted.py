"""Style-adjusted FTAOE: a second, labeled baseline.

Question it answers: how many shooting-foul FTs does a player draw
above what his ATTACK PROFILE predicts? The headline FTAOE compares to
a league-average player; this compares to a league-average player with
the same volume of drives, paint touches and post touches.

Leak-free construction:
  - Features are exposure COUNTS only (drives, paint touches, post
    touches per finisher-possession) from NBA tracking aggregates.
    The player's own FT outcomes on those plays are never features.
  - Player-season grain Poisson GLM with offset log(possessions),
    season cross-fit (train on 5 seasons, predict the 6th), then
    anchored so each season's possession-weighted mean prediction
    equals the season's actual rate among covered players.

Writes style_expected(player_id, season, style_xfta, covered).
"""
from __future__ import annotations

import sqlite3

import numpy as np
import pandas as pd
import statsmodels.api as sm

from config import DB_PATH, SEASONS

QUALIFY_POSS = 300


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    ps = pd.read_sql(
        """SELECT player_id, season, possessions, actual_fta_from_fouls AS fta
           FROM player_season_xfta_poss
           WHERE possessions >= ?""",
        conn,
        params=(QUALIFY_POSS,),
    )
    te = pd.read_sql(
        "SELECT player_id, season, drives, paint_touches, post_touches "
        "FROM tracking_exposures",
        conn,
    )
    df = ps.merge(te, on=["player_id", "season"], how="left")
    covered = df["drives"].notna()
    print(
        f"qualified player-seasons: {len(df)}; with tracking exposures: "
        f"{int(covered.sum())} ({covered.mean() * 100:.1f}%)"
    )
    df = df[covered].copy()

    # Exposure intensities per 100 finisher-possessions.
    for c in ["drives", "paint_touches", "post_touches"]:
        df[f"{c}_per100"] = df[c] / df["possessions"] * 100

    feats = ["drives_per100", "paint_touches_per100", "post_touches_per100"]
    preds = []
    for held in SEASONS:
        tr = df[df["season"] != held]
        teq = df[df["season"] == held].copy()
        if teq.empty:
            continue
        X_tr = sm.add_constant(tr[feats].astype(float), has_constant="add")
        X_te = sm.add_constant(teq[feats].astype(float), has_constant="add")
        model = sm.GLM(
            tr["fta"].values,
            X_tr,
            family=sm.families.Poisson(),
            offset=np.log(tr["possessions"].values),
        ).fit()
        raw = model.predict(X_te, offset=np.log(teq["possessions"].values))
        anchor = teq["fta"].sum() / raw.sum()
        teq["style_xfta"] = raw * anchor
        rho = np.corrcoef(teq["style_xfta"], teq["fta"])[0, 1]
        print(
            f"{held}: n={len(teq)} anchor x{anchor:.4f} "
            f"corr(pred, actual)={rho:.3f} "
            f"params={dict((k, round(float(v), 4)) for k, v in model.params.items())}"
        )
        preds.append(teq[["player_id", "season", "style_xfta"]])

    out = pd.concat(preds, ignore_index=True)
    conn.execute("DROP TABLE IF EXISTS style_expected")
    out.to_sql("style_expected", conn, if_exists="replace", index=False)
    conn.execute(
        "CREATE INDEX idx_style ON style_expected(player_id, season)"
    )
    conn.commit()

    # Sanity: top/bottom style-adjusted, latest season
    chk = df.merge(out, on=["player_id", "season"])
    chk["adj_per100"] = (chk["fta"] - chk["style_xfta"]) / chk["possessions"] * 100
    latest = chk[chk["season"] == SEASONS[-1]]
    names = pd.read_sql(
        "SELECT DISTINCT player_id, player_name FROM player_season", conn
    )
    latest = latest.merge(names, on="player_id", how="left")
    print(f"\n{SEASONS[-1]} style-adjusted top 5:")
    print(
        latest.nlargest(5, "adj_per100")[
            ["player_name", "fta", "style_xfta", "adj_per100"]
        ].to_string(index=False)
    )
    print(f"\n{SEASONS[-1]} style-adjusted bottom 3:")
    print(
        latest.nsmallest(3, "adj_per100")[
            ["player_name", "fta", "style_xfta", "adj_per100"]
        ].to_string(index=False)
    )
    conn.close()


if __name__ == "__main__":
    main()
