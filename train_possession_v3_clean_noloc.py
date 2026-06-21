"""Diagnostic: refit Poisson GLM WITHOUT shot_distance and shot_zone_basic.

User's hypothesis: missingness in those columns is a back-door proxy for
"possession didn't end in a charged FGA" (turnover, fouled miss, pure FT
trip) — the same leak action_type was carrying, just weaker.

Test: refit on the remaining 4 features (period, seconds_remaining,
score_margin, in_bonus). If lift drops to ~4-5% on the same metric, the
leak is verified to be coming from those two columns. If it stays at
~25%, the residual leak is elsewhere.

Writes predictions_poss_clean_noloc so we can compare to the full
feature set.
"""
from __future__ import annotations

import json
import os
import sqlite3

import numpy as np
import pandas as pd
import statsmodels.api as sm

from config import DB_PATH, SEASONS

MODEL_DIR = "model_artifacts"
os.makedirs(MODEL_DIR, exist_ok=True)

CONTINUOUS_FEATURES = [
    "period",
    "seconds_remaining_in_period",
    "score_margin",
    "in_bonus",
]
TARGET = "sfta"


def load_data() -> pd.DataFrame:
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("SELECT * FROM training_possessions_v2", conn)
    conn.close()
    return df


def clean(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["seconds_remaining_in_period"] = df["seconds_remaining_in_period"].fillna(0.0)
    df["score_margin"] = df["score_margin"].fillna(0.0)
    df["in_bonus"] = df["in_bonus"].fillna(0).astype(int)
    return df


def design_matrix(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
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

        result = sm.GLM(y_train, X_train, family=sm.families.Poisson()).fit(
            maxiter=200, method="IRLS"
        )
        xfta = result.predict(X_test).values

        base = float(y_train.mean())
        l = lift_pct(y_test, xfta, base)
        print(f"  lift={l:.3f}%  baseline={base:.4f}  pred={xfta.mean():.4f}  actual={y_test.mean():.4f}")
        fold_metrics.append({
            "season": held_out, "lift_pct": l, "baseline": base,
            "pred_mean": float(xfta.mean()), "actual_mean": float(y_test.mean()),
        })

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
    print(f"\nOOF global lift: {oof_lift:.3f}%  (4 features, no shot_distance/zone)")

    with open(os.path.join(MODEL_DIR, "headline_v3_clean_noloc_metrics.json"), "w") as f:
        json.dump({
            "folds": fold_metrics,
            "oof_mean_pred": float(oof["xfta"].mean()),
            "oof_mean_actual": float(oof["sfta"].mean()),
            "oof_lift_pct": oof_lift,
            "global_baseline": base_global,
        }, f, indent=2)
    return oof


def write_predictions(oof: pd.DataFrame) -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DROP TABLE IF EXISTS predictions_poss_clean_noloc")
    oof.to_sql("predictions_poss_clean_noloc", conn, if_exists="replace", index=False)
    conn.commit()
    conn.close()
    print(f"\nWrote predictions_poss_clean_noloc ({len(oof):,} rows).")


def main() -> None:
    print(f"Loading {len(SEASONS)} seasons from training_possessions_v2...")
    df = load_data()
    print(f"  {len(df):,} possession rows")
    df_clean = clean(df)

    print("\n=== 3-fold season cross-fit (OOF) — NO LOCATION FEATURES ===")
    oof = cross_fit(df_clean)
    write_predictions(oof)
    print("\nDone.")


if __name__ == "__main__":
    main()
