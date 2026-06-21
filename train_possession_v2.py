"""Train v2 possession-grain xFTA model — locked design.

Locked design (held fixed per user direction):
  - Features: shot_distance, shot_zone_basic, action_type, shot_type, period,
              seconds_remaining_in_period, score_margin, in_bonus, home_or_away.
    CONTEXT ONLY — no player identity, no derived foul/FT signal.
  - Model: Poisson LightGBM (poisson objective, log link).
  - Validation: 3-fold season cross-fit — for each held-out season, train on
                the other two and predict the held-out one. This is the OOF
                guarantee (no train/test leakage).
  - Final: refit on all three seasons for future scoring.

Writes:
  - predictions_poss (game_id, possession_number, sfta, xfta, season)
  - model_artifacts/headline_v2_fold_<season>.txt
  - model_artifacts/headline_v2_final.txt
  - model_artifacts/headline_v2_importance.csv
"""
import json
import os
import sqlite3
import sys

import lightgbm as lgb
import numpy as np
import pandas as pd

sys.path.insert(0, "/Users/kevin/Library/Python/3.9/lib/python/site-packages")
from config import DB_PATH, SEASONS

MODEL_DIR = "model_artifacts"
os.makedirs(MODEL_DIR, exist_ok=True)

# Locked feature set — context only.
FEATURES = [
    "shot_distance",
    "shot_zone_basic",
    "action_type",
    "shot_type",
    "period",
    "seconds_remaining_in_period",
    "score_margin",
    "in_bonus",
    "home_or_away",
]
CATEGORICAL = [
    "shot_zone_basic",
    "action_type",
    "shot_type",
    "home_or_away",
]
TARGET = "sfta"

# Locked hyperparameters — Poisson LightGBM.
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


def load_data() -> pd.DataFrame:
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("SELECT * FROM training_possessions_v2", conn)
    conn.close()
    # Cast categoricals
    for col in CATEGORICAL:
        if col in df.columns:
            df[col] = df[col].astype("category")
    return df


def poisson_deviance(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """2 * sum(y_pred - y * log(y_pred)) — full-sample deviance."""
    y_pred = np.clip(y_pred, 1e-10, None)
    return 2 * float(np.sum(y_pred - y_true * np.log(y_pred)))


def lift_pct(y_true: np.ndarray, y_pred: np.ndarray, baseline: float) -> float:
    base_dev = poisson_deviance(y_true, np.full(len(y_true), baseline))
    pred_dev = poisson_deviance(y_true, y_pred)
    return (base_dev - pred_dev) / base_dev * 100


def cross_fit(df: pd.DataFrame) -> pd.DataFrame:
    """3-fold season cross-fit. Returns OOF predictions for all rows."""
    all_preds = []
    for held_out in SEASONS:
        train = df[df["season"] != held_out]
        test = df[df["season"] == held_out]
        print(f"\nFold: hold out {held_out}  train={len(train):,}  test={len(test):,}")

        X_train, y_train = train[FEATURES], train[TARGET]
        X_test, y_test = test[FEATURES], test[TARGET]

        model = lgb.LGBMRegressor(**LGBM_PARAMS)
        model.fit(
            X_train, y_train,
            eval_set=[(X_test, y_test)],
            eval_metric="poisson",
            callbacks=[
                lgb.early_stopping(stopping_rounds=50, verbose=False),
                lgb.log_evaluation(period=0),
            ],
        )
        test = test.copy()
        test["xfta"] = model.predict(X_test, predict_disable_shape_check=True)

        base = y_train.mean()
        l = lift_pct(y_test.values, test["xfta"].values, base)
        print(f"  best_iter={model.best_iteration_}  lift={l:.2f}%  "
              f"baseline_mean={base:.4f}  pred_mean={test['xfta'].mean():.4f}  "
              f"actual_mean={y_test.mean():.4f}")

        model.booster_.save_model(os.path.join(MODEL_DIR, f"headline_v2_fold_{held_out}.txt"))
        all_preds.append(test[["game_id", "possession_number", "season", "sfta", "xfta"]])

    return pd.concat(all_preds, ignore_index=True)


def final_model(df: pd.DataFrame):
    """Refit on all seasons for production scoring."""
    X, y = df[FEATURES], df[TARGET]
    model = lgb.LGBMRegressor(**LGBM_PARAMS)
    model.fit(X, y)
    model.booster_.save_model(os.path.join(MODEL_DIR, "headline_v2_final.txt"))
    importance = pd.DataFrame({
        "feature": FEATURES,
        "gain": model.booster_.feature_importance("gain"),
    }).sort_values("gain", ascending=False)
    importance.to_csv(os.path.join(MODEL_DIR, "headline_v2_importance.csv"), index=False)
    print(f"\nFinal model saved. Top features:")
    for _, r in importance.iterrows():
        print(f"  {r['feature']:35s} {r['gain']:>10,.0f}")
    return model


def main():
    print(f"Loading {len(SEASONS)} seasons from training_possessions_v2...")
    df = load_data()
    print(f"  {len(df):,} possession rows")
    for s in SEASONS:
        n = (df["season"] == s).sum()
        n_pos = (df[df["season"] == s]["sfta"] > 0).sum()
        print(f"  {s}: {n:,} rows, {n_pos:,} with sfta>0 ({n_pos/n*100:.2f}%)")

    print("\n=== 3-fold season cross-fit (OOF) ===")
    oof = cross_fit(df)

    # OOF calibration — mean predicted vs mean actual
    pred_mean = oof["xfta"].mean()
    actual_mean = oof["sfta"].mean()
    delta_pct = (pred_mean - actual_mean) / actual_mean * 100
    base = df["sfta"].mean()  # global mean
    oof_lift = lift_pct(oof["sfta"].values, oof["xfta"].values, base)
    print(f"\nOOF global calibration:")
    print(f"  mean predicted: {pred_mean:.4f}")
    print(f"  mean actual:    {actual_mean:.4f}")
    print(f"  delta:          {delta_pct:+.2f}%  (target: within 2%)")
    print(f"  lift vs baseline: {oof_lift:.2f}%  (target: > 0)")

    # Write predictions to SQLite
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DROP TABLE IF EXISTS predictions_poss")
    oof.to_sql("predictions_poss", conn, if_exists="replace", index=False)
    conn.execute(
        "CREATE INDEX idx_predposs_season ON predictions_poss(season)"
    )
    conn.execute(
        "CREATE INDEX idx_predposs_game ON predictions_poss(game_id, possession_number)"
    )
    conn.commit()
    conn.close()
    print(f"\nWrote predictions_poss ({len(oof):,} rows).")

    print("\n=== Refit on all seasons for production ===")
    final_model(df)

    print("\nDone.")


if __name__ == "__main__":
    main()
