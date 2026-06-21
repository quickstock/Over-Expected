"""Train v3 possession-grain xFTA model — LEAK-CLEAN refit.

Per the Step 0 keep/drop sign-off, this is the post-leak version of
train_possession_v2.py. The previous model was inflated because of
three leaks:

  1. action_type = {made, missed, turnover, other} is literally the
     resolution of the possession — almost a perfect proxy for sfta.
  2. shot_type carried no signal in v2 (only 2pt / unknown), so it
     was a wasted feature that contributed nothing AND masked the fact
     that all made-threes get folded into action_type=other.
  3. LightGBM (2000 trees, num_leaves=63) is a nuclear hammer for 6
     features — gave the model room to memorize the leak.

Locked design (v3, leak-clean):
  - Grain:  one row per possession, target sfta ∈ {0,1,2,3,4,5}.
  - Features (6, all pre-foul context):
        shot_distance, shot_zone_basic, period,
        seconds_remaining_in_period, score_margin, in_bonus
    - shot_distance: NaN → 0 (non-FG-ending possessions; treat as
      "no shot taken at the rim")
    - score_margin:  NULL → 0 (pbpstats doesn't carry a pre-foul
      margin for ~49% of rows; treat as "margin unknown, play on")
    - in_bonus:  Q4+ proxy. Period >= 4 → 1, else 0.
  - Model:  Poisson GLM (log link, no interactions). statsmodels
    Poisson with one-hot encoding of shot_zone_basic. No regularization.
  - Validation:  3-fold season cross-fit. Train on 2 seasons, predict
    the held-out 3rd. Concatenate the OOF xfta, persist to
    predictions_poss_clean.
  - Leaderboard: build_possession_leaderboard on the OOF xfta, then
    side-by-side with the current (leaky) version for the top-20.

Lift target: ~4-5% (down from the inflated 30%+). If it's still
high, the 6 features are still leaking somehow and we revisit.
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys

import numpy as np
import pandas as pd
import statsmodels.api as sm

from config import DB_PATH, SEASONS

MODEL_DIR = "model_artifacts"
os.makedirs(MODEL_DIR, exist_ok=True)

# Locked feature list (4) — post Blocker-1 diagnostic.
# shot_distance and shot_zone_basic removed: their missingness proxies
# possession resolution (64.5% of "unknown zone" possessions are FT
# trips vs 3-9% for charged FGA zones). 4 features is what survives
# the leak-clean refit with OOF lift dropping from 25.3% → 0.1%.
CONTINUOUS_FEATURES = [
    "period",
    "seconds_remaining_in_period",
    "score_margin",
    "in_bonus",
]
CATEGORICAL_FEATURES: list[str] = []
ALL_FEATURES = CONTINUOUS_FEATURES
TARGET = "sfta"


def load_data() -> pd.DataFrame:
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("SELECT * FROM training_possessions_v2", conn)
    conn.close()
    return df


def clean(df: pd.DataFrame) -> pd.DataFrame:
    """Apply the agreed imputation rules. Drops nothing."""
    df = df.copy()
    # score_margin NULL → 0  (pre-foul margin not carried)
    df["score_margin"] = df["score_margin"].fillna(0.0)
    # seconds_remaining NaN → 0  (clock-not-carried possessions)
    df["seconds_remaining_in_period"] = df["seconds_remaining_in_period"].fillna(0.0)
    # in_bonus: any NaN → 0
    df["in_bonus"] = df["in_bonus"].fillna(0).astype(int)
    return df


def design_matrix(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """Build the GLM design matrix. 4 continuous features + intercept."""
    X = pd.DataFrame()
    for col in CONTINUOUS_FEATURES:
        X[col] = df[col].astype(float)
    X = sm.add_constant(X, has_constant="add")
    return X, list(X.columns)


def poisson_deviance(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    y_pred = np.clip(y_pred, 1e-10, None)
    return 2 * float(np.sum(y_pred - y_true * np.log(y_pred)))


def lift_pct(y_true: np.ndarray, y_pred: np.ndarray, baseline: float) -> float:
    base_dev = poisson_deviance(y_true, np.full(len(y_true), baseline))
    pred_dev = poisson_deviance(y_true, y_pred)
    return (base_dev - pred_dev) / base_dev * 100


def cross_fit(df_clean: pd.DataFrame) -> pd.DataFrame:
    """3-fold season cross-fit. OOF predictions for every row."""
    all_preds = []
    fold_metrics = []
    for held_out in SEASONS:
        train = df_clean[df_clean["season"] != held_out]
        test = df_clean[df_clean["season"] == held_out]
        print(f"\nFold: hold out {held_out}  train={len(train):,}  test={len(test):,}")

        X_train, cols = design_matrix(train)
        X_test, _ = design_matrix(test)
        X_test = X_test[cols]

        y_train = train[TARGET].astype(int).values
        y_test = test[TARGET].astype(int).values

        # Poisson GLM with log link. maxiter bumped in case of slow
        # convergence on rare-category cells.
        model = sm.GLM(
            y_train,
            X_train,
            family=sm.families.Poisson(),
        )
        result = model.fit(maxiter=200, method="IRLS")
        xfta = result.predict(X_test).values

        base = float(y_train.mean())
        l = lift_pct(y_test, xfta, base)
        print(f"  lift={l:.3f}%  baseline_mean={base:.4f}  "
              f"pred_mean={xfta.mean():.4f}  actual_mean={y_test.mean():.4f}")
        fold_metrics.append({"season": held_out, "lift_pct": l,
                              "baseline": base, "pred_mean": float(xfta.mean()),
                              "actual_mean": float(y_test.mean())})

        # Persist the fold model
        with open(os.path.join(MODEL_DIR, f"headline_v3_clean_fold_{held_out}.json"), "w") as f:
            json.dump({
                "params": {k: float(v) for k, v in result.params.items()},
                "converged": bool(result.converged),
                "llf": float(result.llf),
                "deviance": float(result.deviance),
                "lift_pct_fold": l,
                "feature_names": cols,
            }, f, indent=2)

        preds = pd.DataFrame({
            "game_id": test["game_id"].values,
            "possession_number": test["possession_number"].values,
            "season": test["season"].values,
            "sfta": y_test,
            "xfta": xfta,
        })
        all_preds.append(preds)

    oof = pd.concat(all_preds, ignore_index=True)
    base_global = float(df_clean[TARGET].mean())
    oof_lift = lift_pct(oof["sfta"].values, oof["xfta"].values, base_global)
    print(f"\nOOF global:")
    print(f"  mean predicted: {oof['xfta'].mean():.4f}")
    print(f"  mean actual:    {oof['sfta'].mean():.4f}")
    print(f"  lift vs baseline (mean sfta = {base_global:.4f}): {oof_lift:.3f}%")

    with open(os.path.join(MODEL_DIR, "headline_v3_clean_metrics.json"), "w") as f:
        json.dump({
            "folds": fold_metrics,
            "oof_mean_pred": float(oof["xfta"].mean()),
            "oof_mean_actual": float(oof["sfta"].mean()),
            "oof_lift_pct": oof_lift,
            "global_baseline": base_global,
        }, f, indent=2)
    return oof


def final_model(df_clean: pd.DataFrame) -> None:
    """Refit on all seasons. Used for production scoring later."""
    X, cols = design_matrix(df_clean)
    y = df_clean[TARGET].astype(int).values
    result = sm.GLM(y, X, family=sm.families.Poisson()).fit(maxiter=200, method="IRLS")
    out = {
        "params": {k: float(v) for k, v in result.params.items()},
        "converged": bool(result.converged),
        "llf": float(result.llf),
        "deviance": float(result.deviance),
        "feature_names": cols,
    }
    with open(os.path.join(MODEL_DIR, "headline_v3_clean_final.json"), "w") as f:
        json.dump(out, f, indent=2)
    print("\nFinal model:")
    for k, v in result.params.items():
        print(f"  {k:35s} {v:+.5f}")


def write_predictions(oof: pd.DataFrame) -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DROP TABLE IF EXISTS predictions_poss_clean")
    oof.to_sql("predictions_poss_clean", conn, if_exists="replace", index=False)
    conn.execute(
        "CREATE INDEX idx_predclean_season ON predictions_poss_clean(season)"
    )
    conn.execute(
        "CREATE INDEX idx_predclean_game ON predictions_poss_clean(game_id, possession_number)"
    )
    conn.commit()
    conn.close()
    print(f"\nWrote predictions_poss_clean ({len(oof):,} rows).")


def main() -> None:
    print(f"Loading {len(SEASONS)} seasons from training_possessions_v2...")
    df = load_data()
    print(f"  {len(df):,} possession rows")
    for s in SEASONS:
        n = (df["season"] == s).sum()
        n_pos = (df[df["season"] == s]["sfta"] > 0).sum()
        print(f"  {s}: {n:,} rows, {n_pos:,} with sfta>0 ({n_pos/n*100:.2f}%)")

    print("\nCleaning: NaN imputation per locked design...")
    df_clean = clean(df)
    print(f"  shot_distance NaN→0: now {df_clean['shot_distance'].isna().sum()} NaN")
    print(f"  score_margin NaN→0:  now {df_clean['score_margin'].isna().sum()} NaN")
    print(f"  in_bonus: {df_clean['in_bonus'].value_counts().to_dict()}")

    print("\n=== 3-fold season cross-fit (OOF) ===")
    oof = cross_fit(df_clean)
    write_predictions(oof)

    print("\n=== Refit on all seasons for production ===")
    final_model(df_clean)

    print("\nDone.")


if __name__ == "__main__":
    main()
