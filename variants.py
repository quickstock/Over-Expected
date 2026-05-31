"""xFTA Phase 2 — Variant comparisons.

1. Archetype variant: add shooter_height + shooter_position to headline model.
   Compare leaderboards via Spearman rank correlation + top movers.

2. Multiclass calibration: 4-class LightGBM (0/1/2/3), derive xFTA as
   expected value, compare calibration to Poisson.
"""

import os

import lightgbm as lgb
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from config import (
    DB_PATH,
    HEADLINE_FEATURES,
    HELD_OUT_FEATURES,
    SEASONS,
    TARGET,
)

MODEL_DIR = "model_artifacts"

CATEGORICAL_FEATURES = [
    "shot_zone_basic",
    "shot_zone_area",
    "action_type",
    "shot_type",
    "home_or_away",
    "shooter_position",  # added for archetype
]

LGBM_PARAMS = {
    "objective": "poisson",
    "learning_rate": 0.05,
    "num_leaves": 63,
    "min_child_samples": 200,
    "feature_fraction": 0.8,
    "bagging_fraction": 0.8,
    "bagging_freq": 1,
    "verbose": -1,
    "n_estimators": 2000,
}

MULTICLASS_PARAMS = {
    "objective": "multiclass",
    "num_class": 3,
    "learning_rate": 0.05,
    "num_leaves": 63,
    "min_child_samples": 200,
    "feature_fraction": 0.8,
    "bagging_fraction": 0.8,
    "bagging_freq": 1,
    "verbose": -1,
    "n_estimators": 2000,
}


def load_data():
    import sqlite3
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("SELECT * FROM training_fga", conn)
    conn.close()
    for col in CATEGORICAL_FEATURES:
        if col in df.columns:
            df[col] = df[col].astype("category")
    return df


def prepare_features(df, features):
    cols = features + [TARGET, "game_id", "event_id", "player_id", "season"]
    return df[cols].dropna(subset=features)


def poisson_deviance(y_true, y_pred):
    y_pred = np.clip(y_pred, 1e-10, None)
    return 2 * np.sum(y_pred - y_true * np.log(y_pred))


def run_archetype_variant(df):
    """Train archetype model with shooter_height + shooter_position."""
    archetype_features = HEADLINE_FEATURES + ["shooter_height", "shooter_position"]
    print("=" * 60)
    print("VARIANT 1: ARCHETYPE (height + position)")
    print("=" * 60)

    all_predictions = []
    for held_out in SEASONS:
        train_seasons = [s for s in SEASONS if s != held_out]
        train = prepare_features(df[df["season"].isin(train_seasons)], archetype_features)
        test = prepare_features(df[df["season"] == held_out], archetype_features)

        model = lgb.LGBMRegressor(**LGBM_PARAMS)
        model.fit(
            train[archetype_features], train[TARGET],
            eval_set=[(test[archetype_features], test[TARGET])],
            eval_metric="poisson",
            callbacks=[
                lgb.early_stopping(stopping_rounds=50, verbose=False),
                lgb.log_evaluation(period=0),
            ],
        )
        test = test.copy()
        test["xfta_archetype"] = model.predict(test[archetype_features], predict_disable_shape_check=True)
        all_predictions.append(test[["game_id", "event_id", "player_id", "season",
                                     "fta_from_shot", "xfta_archetype"]])
        print(f"  Fold {held_out}: best_iter={model.best_iteration_}")

    predictions = pd.concat(all_predictions, ignore_index=True)

    # Load headline predictions for comparison
    headline = pd.read_csv(os.path.join(MODEL_DIR, "cross_fit_predictions.csv"))

    # Build leaderboards for both
    import sqlite3
    conn = sqlite3.connect(DB_PATH)
    player = pd.read_sql("SELECT player_id, player_name, season FROM player_season", conn)
    conn.close()

    def build_lb(preds, xfta_col):
        lb = preds.merge(player, on=["player_id", "season"], how="left")
        result = lb.groupby(["player_id", "season"]).agg(
            player_name=("player_name", "first"),
            fga=("fta_from_shot", "count"),
            actual_fta=("fta_from_shot", "sum"),
            xfta_total=(xfta_col, "sum"),
        ).reset_index()
        result["ftaoe"] = result["actual_fta"] - result["xfta_total"]
        result["ftaoe_per_100"] = result["ftaoe"] / result["fga"] * 100
        return result

    lb_headline = build_lb(headline, "xfta")
    lb_archetype = build_lb(predictions, "xfta_archetype")

    # Merge for correlation
    merged = lb_headline.merge(lb_archetype, on=["player_id", "season"],
                                suffixes=("_headline", "_archetype"))

    # Filter min 100 FGA
    merged = merged[(merged["fga_headline"] >= 100) & (merged["fga_archetype"] >= 100)]

    # Spearman rank correlation of top-100
    top100_h = merged.nlargest(100, "ftaoe_per_100_headline")
    top100_a = merged.nlargest(100, "ftaoe_per_100_archetype")

    # Top-100 overlap
    common = set(top100_h["player_id"].astype(str) + "_" + top100_h["season"]) & \
             set(top100_a["player_id"].astype(str) + "_" + top100_a["season"])

    # Overall Spearman
    rho, pval = spearmanr(merged["ftaoe_per_100_headline"], merged["ftaoe_per_100_archetype"])

    print(f"\n  Overall Spearman rho: {rho:.4f} (p={pval:.2e})")
    print(f"  Top-100 overlap: {len(common)}/100")

    # Top movers
    merged["rank_diff"] = merged["ftaoe_per_100_archetype"] - merged["ftaoe_per_100_headline"]
    print("\n  TOP 10 MOVERS (archetype − headline, FTAOE/100):")
    print("  Players who gain most from height/position info:")
    top_movers = merged.nlargest(10, "rank_diff")
    for _, r in top_movers.iterrows():
        print(f"    {r['player_name_headline']:25s} {r['season']}  "
              f"headline={r['ftaoe_per_100_headline']:+.2f}  "
              f"archetype={r['ftaoe_per_100_archetype']:+.2f}  "
              f"diff={r['rank_diff']:+.2f}")

    print("\n  Players who lose most from height/position info:")
    bot_movers = merged.nsmallest(10, "rank_diff")
    for _, r in bot_movers.iterrows():
        print(f"    {r['player_name_headline']:25s} {r['season']}  "
              f"headline={r['ftaoe_per_100_headline']:+.2f}  "
              f"archetype={r['ftaoe_per_100_archetype']:+.2f}  "
              f"diff={r['rank_diff']:+.2f}")

    # Side-by-side top-30
    print("\n  SIDE-BY-SIDE TOP-30:")
    h30 = lb_headline[lb_headline["fga"] >= 100].nlargest(30, "ftaoe_per_100")
    a30 = lb_archetype[lb_archetype["fga"] >= 100].nlargest(30, "ftaoe_per_100")
    print(f"  {'Rank':>4s}  {'Headline':>25s}  {'FTAOE/100':>9s}  |  {'Archetype':>25s}  {'FTAOE/100':>9s}")
    for i in range(30):
        h = h30.iloc[i] if i < len(h30) else pd.Series()
        a = a30.iloc[i] if i < len(a30) else pd.Series()
        hname = h.get("player_name", "")
        hval = h.get("ftaoe_per_100", 0)
        aname = a.get("player_name", "")
        aval = a.get("ftaoe_per_100", 0)
        print(f"  {i+1:>4d}  {hname:>25s}  {hval:>+9.2f}  |  {aname:>25s}  {aval:>+9.2f}")

    # Save archetype model artifacts
    model.booster_.save_model(os.path.join(MODEL_DIR, "archetype_gate_a.txt"))
    predictions.to_csv(os.path.join(MODEL_DIR, "archetype_predictions.csv"), index=False)
    print(f"\n  Archetype artifacts saved to {MODEL_DIR}/")


def run_multiclass_variant(df):
    """Train multiclass LightGBM (0/1/2/3), derive xFTA as expected value."""
    print("\n" + "=" * 60)
    print("VARIANT 2: MULTICLASS (4-class, derive xFTA as E[P(class)*value])")
    print("=" * 60)

    all_predictions = []
    for held_out in SEASONS:
        train_seasons = [s for s in SEASONS if s != held_out]
        train = prepare_features(df[df["season"].isin(train_seasons)], HEADLINE_FEATURES)
        test = prepare_features(df[df["season"] == held_out], HEADLINE_FEATURES)

        model = lgb.LGBMClassifier(**MULTICLASS_PARAMS)
        model.fit(
            train[HEADLINE_FEATURES], train[TARGET],
            eval_set=[(test[HEADLINE_FEATURES], test[TARGET])],
            callbacks=[
                lgb.early_stopping(stopping_rounds=50, verbose=False),
                lgb.log_evaluation(period=0),
            ],
        )

        probs = model.predict_proba(test[HEADLINE_FEATURES])
        test = test.copy()
        # xFTA = E[FTA] = sum(value * P(value)); classes are 0, 1, 2
        test["xfta_multi"] = probs[:, 1] * 1 + probs[:, 2] * 2
        all_predictions.append(test[["game_id", "event_id", "player_id", "season",
                                     "fta_from_shot", "xfta_multi"]])
        print(f"  Fold {held_out}: best_iter={model.best_iteration_}")

    predictions = pd.concat(all_predictions, ignore_index=True)

    # Poisson deviance comparison
    dev_poisson = poisson_deviance(predictions["fta_from_shot"], predictions["xfta_multi"])
    headline = pd.read_csv(os.path.join(MODEL_DIR, "cross_fit_predictions.csv"))
    dev_headline = poisson_deviance(headline["fta_from_shot"], headline["xfta"])

    print(f"\n  Multiclass Poisson deviance:  {dev_poisson:,.2f}")
    print(f"  Headline Poisson deviance:     {dev_headline:,.2f}")

    # Calibration comparison
    for name, preds_df, xfta_col in [
        ("Poisson (headline)", headline, "xfta"),
        ("Multiclass", predictions, "xfta_multi"),
    ]:
        df_cal = preds_df.copy()
        df_cal["decile"] = pd.qcut(df_cal[xfta_col], q=10, labels=False, duplicates="drop")
        cal = df_cal.groupby("decile").agg(
            pred=(xfta_col, "mean"),
            actual=("fta_from_shot", "mean"),
        ).reset_index()
        print(f"\n  {name} calibration:")
        print(f"  {'Decile':>6s}  {'Pred':>10s}  {'Actual':>10s}")
        for _, r in cal.iterrows():
            print(f"  {int(r['decile']):>6d}  {r['pred']:>10.4f}  {r['actual']:>10.4f}")

    # Calibration plots side by side
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    for ax, (name, preds_df, xfta_col) in zip(axes, [
        ("Poisson", headline, "xfta"),
        ("Multiclass", predictions, "xfta_multi"),
    ]):
        df_cal = preds_df.copy()
        df_cal["decile"] = pd.qcut(df_cal[xfta_col], q=10, labels=False, duplicates="drop")
        cal = df_cal.groupby("decile").agg(
            pred=(xfta_col, "mean"),
            actual=("fta_from_shot", "mean"),
            count=("fta_from_shot", "count"),
        ).reset_index()
        ax.scatter(cal["pred"], cal["actual"], s=cal["count"] / 50, alpha=0.7, color="#E8600A")
        max_val = max(cal["pred"].max(), cal["actual"].max()) * 1.1
        ax.plot([0, max_val], [0, max_val], "--", color="gray", alpha=0.5)
        ax.set_xlabel("Predicted xFTA")
        ax.set_ylabel("Actual FTA per shot")
        ax.set_title(f"{name} Calibration")
        ax.set_xlim(0, max_val)
        ax.set_ylim(0, max_val)

    plt.tight_layout()
    path = os.path.join(MODEL_DIR, "calibration_poisson_vs_multiclass.png")
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"\n  Side-by-side calibration plot saved: {path}")

    # Save multiclass artifacts
    model.booster_.save_model(os.path.join(MODEL_DIR, "multiclass_gate_a.txt"))
    predictions.to_csv(os.path.join(MODEL_DIR, "multiclass_predictions.csv"), index=False)


if __name__ == "__main__":
    df = load_data()
    print(f"Loaded {len(df):,} rows")

    run_archetype_variant(df)
    run_multiclass_variant(df)

    print("\n" + "=" * 60)
    print("VARIANT COMPARISONS COMPLETE")
    print("=" * 60)