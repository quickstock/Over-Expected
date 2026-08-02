"""Archetype variant, re-run against the CURRENT possession model.

The original test (variants.py, deleted at e4a49a8) ran on the FGA-grain
`fta_from_shot` target, which was later found wrong and abandoned. Its result
(a Spearman rho) was printed to stdout and never saved, so it is unciteable.
This is the same question asked of the model that actually ships.

The question: FTAOE's headline model is context-only by design. It never sees
who is shooting. If you hand the model the finisher's identity — height,
position, and his own prior-season free-throw rate — does the leaderboard
change? If the ranking survives, "context-only" is a defensible modelling
choice rather than a limitation, and FTAOE is measuring something the identity
features do not already encode.

Three arms, identical folds, identical anchoring:

  headline   the 7 production features (imported from the production module,
             so this arm is the shipping model by construction)
  archetype  + finisher height + finisher position        (the original test)
  identity   + prior-season FTr + a missingness indicator (the strong test:
             prior FTr is a direct measure of the thing FTAOE measures, so
             this arm deliberately lets the model explain away the signal)

A high rank correlation between headline and identity is the meaningful
result. It says the leaderboard is not an artefact of withholding identity.

Writes model_artifacts/variant_archetype.json.
"""
from __future__ import annotations

import json
import os
import sqlite3

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.stats import spearmanr, pearsonr

from config import DB_PATH, SEASONS
from train_possession_v4_context import (
    FEATURES as HEADLINE_FEATURES,
    TARGET,
    load,
    poisson_deviance,
)

MODEL_DIR = "model_artifacts"
QUALIFY_POSS = 300

# Production FTAOE for Giannis 2024-25, from the pre-publication audit
# (paper/experiment_record.md:101). The headline arm must reproduce it, or the
# harness is not measuring the shipping model and no variant result is worth
# anything.
PRODUCTION_CHECK = {
    "player_name": "Giannis Antetokounmpo",
    "season": "2024-25",
    "ftaoe": 311.8,
    "tol": 1.0,
}


def attach_identity(df: pd.DataFrame) -> pd.DataFrame:
    """Join the finisher's identity attributes onto each possession.

    Height and position are static and cover every player-season. Prior-season
    FTr is missing for rookies and for anyone absent the year before, so it is
    mean-imputed within the fold's training seasons and paired with an explicit
    missingness indicator — the model is told the value was absent rather than
    being fed a silent league-average.
    """
    conn = sqlite3.connect(DB_PATH)
    fin = pd.read_sql(
        "SELECT game_id, possession_number, finisher_player_id FROM possessions",
        conn,
    )
    ps = pd.read_sql(
        "SELECT player_id, season, player_name, height_inches, position, "
        "prior_season_ftr FROM player_season",
        conn,
    )
    conn.close()

    df = df.merge(fin, on=["game_id", "possession_number"], how="left")
    df["finisher_player_id"] = df["finisher_player_id"].astype("Int64")
    ps = ps.rename(columns={"player_id": "finisher_player_id"})
    ps["finisher_player_id"] = ps["finisher_player_id"].astype("Int64")
    df = df.merge(ps, on=["finisher_player_id", "season"], how="left")

    n_fin = int(df["has_finisher"].sum())
    n_h = int(df.loc[df["has_finisher"].astype(bool), "height_inches"].notna().sum())
    n_f = int(df.loc[df["has_finisher"].astype(bool), "prior_season_ftr"].notna().sum())
    print(
        f"identity join: {n_fin:,} finisher possessions; "
        f"height on {n_h:,} ({n_h / n_fin:.1%}); "
        f"prior FTr on {n_f:,} ({n_f / n_fin:.1%})"
    )

    # Height: league-mean fill for the non-finisher possessions (they carry
    # sfta == 0 by construction and never reach a leaderboard).
    df["height_inches"] = df["height_inches"].astype(float)
    df["f_height"] = df["height_inches"].fillna(df["height_inches"].mean())

    # Position: one-hot, drop-first. Non-finisher rows get an explicit "None"
    # level rather than being silently folded into the reference category.
    pos = df["position"].fillna("None").astype(str)
    dummies = pd.get_dummies(pos, prefix="f_pos", drop_first=True).astype(float)
    df = pd.concat([df, dummies], axis=1)

    df["f_prior_ftr_missing"] = df["prior_season_ftr"].isna().astype(float)
    df["f_prior_ftr_raw"] = df["prior_season_ftr"].astype(float)

    return df, list(dummies.columns)


def fit_arm(train, test, features, fin_mask_test):
    """One Poisson GLM fold, anchored exactly as production anchors."""
    X_tr = sm.add_constant(train[features].astype(float), has_constant="add")
    X_te = sm.add_constant(test[features].astype(float), has_constant="add")
    model = sm.GLM(
        train[TARGET].values, X_tr, family=sm.families.Poisson()
    ).fit()
    raw = model.predict(X_te).values

    season_mean = float(test.loc[fin_mask_test, TARGET].mean())
    anchor = season_mean / float(raw[fin_mask_test].mean())
    xfta = raw * anchor

    base_dev = poisson_deviance(
        test[TARGET].values[fin_mask_test],
        np.full(int(fin_mask_test.sum()), season_mean),
    )
    pred_dev = poisson_deviance(
        test[TARGET].values[fin_mask_test], xfta[fin_mask_test]
    )
    lift = (base_dev - pred_dev) / base_dev * 100
    return xfta, lift, anchor


def leaderboard(df: pd.DataFrame, xfta_col: str) -> pd.DataFrame:
    """FTAOE per player-season at the production grain: finisher possessions
    only, actual minus summed expected, qualified at >= 300 possessions."""
    fin = df[df["has_finisher"].astype(bool) & df["finisher_player_id"].notna()]
    lb = (
        fin.groupby(["finisher_player_id", "season"])
        .agg(
            player_name=("player_name", "first"),
            possessions=("sfta", "size"),
            actual_fta=("sfta", "sum"),
            xfta_total=(xfta_col, "sum"),
        )
        .reset_index()
    )
    lb["ftaoe"] = lb["actual_fta"] - lb["xfta_total"]
    lb["ftaoe_per_100"] = lb["ftaoe"] / lb["possessions"] * 100
    return lb[lb["possessions"] >= QUALIFY_POSS].copy()


def compare(lb_a: pd.DataFrame, lb_b: pd.DataFrame, name_a: str, name_b: str):
    m = lb_a.merge(
        lb_b, on=["finisher_player_id", "season"], suffixes=("_a", "_b")
    )
    rho, rho_p = spearmanr(m["ftaoe_per_100_a"], m["ftaoe_per_100_b"])
    r, _ = pearsonr(m["ftaoe_per_100_a"], m["ftaoe_per_100_b"])

    # Ranks within season, which is how the board is actually read.
    m["rank_a"] = m.groupby("season")["ftaoe_a"].rank(ascending=False, method="min")
    m["rank_b"] = m.groupby("season")["ftaoe_b"].rank(ascending=False, method="min")
    m["rank_shift"] = (m["rank_a"] - m["rank_b"]).abs()

    overlaps = {}
    for k in (10, 25, 50, 100):
        top_a = set(
            m.nlargest(k, "ftaoe_per_100_a")["finisher_player_id"].astype(str)
            + "_" + m.nlargest(k, "ftaoe_per_100_a")["season"]
        )
        top_b = set(
            m.nlargest(k, "ftaoe_per_100_b")["finisher_player_id"].astype(str)
            + "_" + m.nlargest(k, "ftaoe_per_100_b")["season"]
        )
        overlaps[f"top{k}"] = len(top_a & top_b)

    m["delta"] = m["ftaoe_per_100_b"] - m["ftaoe_per_100_a"]
    movers_up = m.nlargest(8, "delta")[
        ["player_name_a", "season", "ftaoe_per_100_a", "ftaoe_per_100_b", "delta"]
    ]
    movers_dn = m.nsmallest(8, "delta")[
        ["player_name_a", "season", "ftaoe_per_100_a", "ftaoe_per_100_b", "delta"]
    ]

    print(f"\n--- {name_a} vs {name_b}  (n = {len(m):,} qualified player-seasons)")
    print(f"  Spearman rho : {rho:.4f}  (p = {rho_p:.3e})")
    print(f"  Pearson r    : {r:.4f}")
    print(f"  top-N overlap: " + "  ".join(f"{k}={v}" for k, v in overlaps.items()))
    print(
        f"  rank shift   : mean {m['rank_shift'].mean():.2f}  "
        f"p95 {m['rank_shift'].quantile(0.95):.0f}  max {m['rank_shift'].max():.0f}"
    )
    print(f"  |delta/100|  : mean {m['delta'].abs().mean():.3f}  "
          f"max {m['delta'].abs().max():.3f}")
    print(f"  biggest gainers under {name_b}:")
    for _, r_ in movers_up.iterrows():
        print(f"    {r_['player_name_a']:26s} {r_['season']}  "
              f"{r_['ftaoe_per_100_a']:+7.2f} -> {r_['ftaoe_per_100_b']:+7.2f}"
              f"  ({r_['delta']:+.2f})")
    print(f"  biggest losers under {name_b}:")
    for _, r_ in movers_dn.iterrows():
        print(f"    {r_['player_name_a']:26s} {r_['season']}  "
              f"{r_['ftaoe_per_100_a']:+7.2f} -> {r_['ftaoe_per_100_b']:+7.2f}"
              f"  ({r_['delta']:+.2f})")

    return {
        "comparison": f"{name_a}_vs_{name_b}",
        "nPlayerSeasons": int(len(m)),
        "spearmanRho": round(float(rho), 4),
        "spearmanP": float(rho_p),
        "pearsonR": round(float(r), 4),
        "topNOverlap": overlaps,
        "rankShiftMean": round(float(m["rank_shift"].mean()), 3),
        "rankShiftP95": float(m["rank_shift"].quantile(0.95)),
        "rankShiftMax": float(m["rank_shift"].max()),
        "meanAbsDeltaPer100": round(float(m["delta"].abs().mean()), 4),
        "maxAbsDeltaPer100": round(float(m["delta"].abs().max()), 4),
        "topGainers": [
            {"player": r_["player_name_a"], "season": r_["season"],
             "base": round(float(r_["ftaoe_per_100_a"]), 3),
             "variant": round(float(r_["ftaoe_per_100_b"]), 3),
             "delta": round(float(r_["delta"]), 3)}
            for _, r_ in movers_up.iterrows()
        ],
        "topLosers": [
            {"player": r_["player_name_a"], "season": r_["season"],
             "base": round(float(r_["ftaoe_per_100_a"]), 3),
             "variant": round(float(r_["ftaoe_per_100_b"]), 3),
             "delta": round(float(r_["delta"]), 3)}
            for _, r_ in movers_dn.iterrows()
        ],
    }


def main() -> None:
    df = load()
    df, pos_cols = attach_identity(df)

    arms = {
        "headline": list(HEADLINE_FEATURES),
        "archetype": list(HEADLINE_FEATURES) + ["f_height"] + pos_cols,
        "identity": list(HEADLINE_FEATURES) + ["f_height"] + pos_cols
        + ["f_prior_ftr", "f_prior_ftr_missing"],
    }
    for name, feats in arms.items():
        print(f"arm {name}: {len(feats)} features")

    fold_lift = {k: [] for k in arms}
    for held in SEASONS:
        tr_mask = df["season"] != held
        te_mask = df["season"] == held
        train = df[tr_mask]
        test = df[te_mask].copy()
        fin_te = test["has_finisher"].values.astype(bool)

        # Prior FTr imputed from the TRAINING seasons only, so the held-out
        # season never informs its own feature.
        tr_mean_ftr = float(train["f_prior_ftr_raw"].mean())
        train = train.assign(
            f_prior_ftr=train["f_prior_ftr_raw"].fillna(tr_mean_ftr)
        )
        test["f_prior_ftr"] = test["f_prior_ftr_raw"].fillna(tr_mean_ftr)

        print(f"\nFold {held}: train={len(train):,} test={len(test):,}")
        for name, feats in arms.items():
            xfta, lift, anchor = fit_arm(train, test, feats, fin_te)
            df.loc[te_mask, f"xfta_{name}"] = xfta
            fold_lift[name].append({"season": held, "lift_pct": lift,
                                    "anchor": anchor})
            print(f"  {name:10s} anchor x{anchor:.4f}  lift {lift:.3f}%")

    boards = {name: leaderboard(df, f"xfta_{name}") for name in arms}

    # Gate: the headline arm must reproduce the shipping leaderboard.
    chk = boards["headline"]
    row = chk[
        (chk["player_name"] == PRODUCTION_CHECK["player_name"])
        & (chk["season"] == PRODUCTION_CHECK["season"])
    ]
    assert len(row) == 1, "production check row not found"
    got = float(row["ftaoe"].iloc[0])
    delta = abs(got - PRODUCTION_CHECK["ftaoe"])
    print(
        f"\nproduction check — {PRODUCTION_CHECK['player_name']} "
        f"{PRODUCTION_CHECK['season']}: FTAOE {got:.1f} "
        f"(shipping {PRODUCTION_CHECK['ftaoe']}, delta {delta:.2f})"
    )
    assert delta <= PRODUCTION_CHECK["tol"], (
        f"headline arm does not reproduce the shipping leaderboard "
        f"({got:.2f} vs {PRODUCTION_CHECK['ftaoe']}). No variant result is "
        f"interpretable until this passes."
    )
    print("  PASS — headline arm reproduces production.")

    results = {
        "question": (
            "Does handing the context-only FTAOE model the finisher's identity "
            "(height, position, prior-season FTr) change the leaderboard?"
        ),
        "design": (
            "Three Poisson GLM arms on identical 6-fold season cross-fit folds "
            "with identical per-season anchoring on the finisher universe. "
            "Prior-season FTr mean-imputed from training seasons only, with an "
            "explicit missingness indicator."
        ),
        "qualifyPossessions": QUALIFY_POSS,
        "arms": {
            name: {
                "nFeatures": len(feats),
                "features": feats,
                "foldLift": [
                    {"season": f["season"], "liftPct": round(f["lift_pct"], 4),
                     "anchor": round(f["anchor"], 5)}
                    for f in fold_lift[name]
                ],
                "meanFoldLiftPct": round(
                    float(np.mean([f["lift_pct"] for f in fold_lift[name]])), 4
                ),
                "nQualified": int(len(boards[name])),
            }
            for name, feats in arms.items()
        },
        "productionCheck": {
            "player": PRODUCTION_CHECK["player_name"],
            "season": PRODUCTION_CHECK["season"],
            "shipping": PRODUCTION_CHECK["ftaoe"],
            "reproduced": round(got, 2),
            "delta": round(delta, 3),
            "passed": True,
        },
        "comparisons": [
            compare(boards["headline"], boards["archetype"],
                    "headline", "archetype"),
            compare(boards["headline"], boards["identity"],
                    "headline", "identity"),
        ],
    }

    out = os.path.join(MODEL_DIR, "variant_archetype.json")
    with open(out, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nwrote {out}")

    # Per-arm boards, merged, for the paper's scatter figure.
    merged = boards["headline"][
        ["finisher_player_id", "season", "player_name", "possessions",
         "actual_fta", "ftaoe", "ftaoe_per_100"]
    ].rename(columns={"ftaoe": "ftaoe_headline",
                      "ftaoe_per_100": "ftaoe_per_100_headline"})
    for name in ("archetype", "identity"):
        merged = merged.merge(
            boards[name][["finisher_player_id", "season", "ftaoe",
                          "ftaoe_per_100"]].rename(
                columns={"ftaoe": f"ftaoe_{name}",
                         "ftaoe_per_100": f"ftaoe_per_100_{name}"}),
            on=["finisher_player_id", "season"], how="inner",
        )
    csv_out = os.path.join(MODEL_DIR, "variant_archetype_boards.csv")
    merged.to_csv(csv_out, index=False)
    print(f"wrote {csv_out}  ({len(merged):,} qualified player-seasons)")


if __name__ == "__main__":
    main()
