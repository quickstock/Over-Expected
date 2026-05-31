"""xFTA Phase 2 — Train headline Poisson LightGBM model.

Gate A: single split (train 2022-23 + 2023-24, test 2024-25).
Gate B: 3-fold season cross-fit + final all-seasons model (run after Gate A approval).
"""

import json
import os
import sqlite3

import lightgbm as lgb
import numpy as np
import pandas as pd

from config import (
    DB_PATH,
    HEADLINE_FEATURES,
    HELD_OUT_FEATURES,
    SEASONS,
    TARGET,
)

MODEL_DIR = "model_artifacts"
os.makedirs(MODEL_DIR, exist_ok=True)

CATEGORICAL_FEATURES = [
    "shot_zone_basic",
    "shot_zone_area",
    "action_type",
    "shot_type",
    "home_or_away",
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


def load_data():
    """Load training_fga from SQLite."""
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("SELECT * FROM training_fga", conn)
    conn.close()

    # Assert no held-out features in headline set
    leak_cols = set(HEADLINE_FEATURES) & set(HELD_OUT_FEATURES)
    assert not leak_cols, f"Headline features contain held-out columns: {leak_cols}"

    # Cast categoricals
    for col in CATEGORICAL_FEATURES:
        if col in df.columns:
            df[col] = df[col].astype("category")

    return df


def split_gate_a(df):
    """Gate A: train on 2022-23 + 2023-24, test on 2024-25."""
    train = df[df["season"].isin(["2022-23", "2023-24"])].copy()
    test = df[df["season"] == "2024-25"].copy()
    return train, test


def prepare_features(df):
    """Select headline features + target, drop rows with null headline features."""
    cols = HEADLINE_FEATURES + [TARGET, "game_id", "event_id", "player_id", "season"]
    df = df[cols].dropna(subset=HEADLINE_FEATURES)
    return df


def train_gate_a(df):
    """Train Gate A model, save model + predictions + metrics."""
    train, test = split_gate_a(df)
    train = prepare_features(train)
    test = prepare_features(test)

    X_train = train[HEADLINE_FEATURES]
    y_train = train[TARGET]
    X_test = test[HEADLINE_FEATURES]
    y_test = test[TARGET]

    model = lgb.LGBMRegressor(**LGBM_PARAMS)
    model.fit(
        X_train,
        y_train,
        eval_set=[(X_test, y_test)],
        eval_metric="poisson",
        callbacks=[
            lgb.early_stopping(stopping_rounds=50, verbose=False),
            lgb.log_evaluation(period=0),
        ],
    )

    # Predictions
    train["xfta"] = model.predict(X_train, predict_disable_shape_check=True)
    test["xfta"] = model.predict(X_test, predict_disable_shape_check=True)

    # Naive baseline: train-set mean
    baseline_pred = y_train.mean()

    # Poisson deviance
    def poisson_deviance(y_true, y_pred):
        y_pred = np.clip(y_pred, 1e-10, None)
        return 2 * np.sum(y_pred - y_true * np.log(y_pred))

    test_deviance = poisson_deviance(y_test, test["xfta"])
    baseline_deviance = poisson_deviance(y_test, np.full(len(y_test), baseline_pred))
    train_deviance = poisson_deviance(y_train, train["xfta"])

    metrics = {
        "gate": "A",
        "train_size": len(train),
        "test_size": len(test),
        "train_poisson_deviance": round(train_deviance, 2),
        "test_poisson_deviance": round(test_deviance, 2),
        "baseline_poisson_deviance": round(baseline_deviance, 2),
        "baseline_mean_fta": round(baseline_pred, 6),
        "lift_vs_baseline_pct": round(
            (baseline_deviance - test_deviance) / baseline_deviance * 100, 2
        ),
        "best_iteration": model.best_iteration_,
    }

    # Save model
    model.booster_.save_model(os.path.join(MODEL_DIR, "headline_gate_a.txt"))

    # Save metrics
    with open(os.path.join(MODEL_DIR, "metrics_gate_a.json"), "w") as f:
        json.dump(metrics, f, indent=2)

    # Save feature importance
    importance = pd.DataFrame({
        "feature": HEADLINE_FEATURES,
        "gain": model.booster_.feature_importance("gain"),
    }).sort_values("gain", ascending=False)
    importance.to_csv(os.path.join(MODEL_DIR, "feature_importance.csv"), index=False)

    # Save test predictions for evaluate.py
    test[["game_id", "event_id", "player_id", "season", "fta_from_shot", "xfta"]
          + HEADLINE_FEATURES].to_csv(
        os.path.join(MODEL_DIR, "gate_a_test_predictions.csv"), index=False
    )

    # Save full test set with all original columns merged
    full_test = df[df["season"] == "2024-25"].copy()
    full_test.loc[test.index, "xfta"] = test["xfta"].values
    full_test.to_csv(os.path.join(MODEL_DIR, "gate_a_test_full.csv"), index=False)

    return model, metrics, train, test


def train_cross_fit(df):
    """Gate B: 3-fold season cross-fit + final all-seasons model.

    For each season, train on the other two and predict that season.
    Then train one final model on all three seasons for future scoring.
    """
    all_predictions = []

    for held_out_season in SEASONS:
        train_seasons = [s for s in SEASONS if s != held_out_season]
        train = df[df["season"].isin(train_seasons)].copy()
        test = df[df["season"] == held_out_season].copy()
        train = prepare_features(train)
        test = prepare_features(test)

        X_train = train[HEADLINE_FEATURES]
        y_train = train[TARGET]
        X_test = test[HEADLINE_FEATURES]
        y_test = test[TARGET]

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

        test["xfta"] = model.predict(X_test, predict_disable_shape_check=True)
        all_predictions.append(test[["game_id", "event_id", "player_id", "season",
                                     "fta_from_shot", "xfta"]])
        print(f"  Fold {held_out_season}: {len(test):,} shots, "
              f"best_iter={model.best_iteration_}")

    predictions = pd.concat(all_predictions, ignore_index=True)

    # Save cross-fit predictions
    predictions.to_csv(os.path.join(MODEL_DIR, "cross_fit_predictions.csv"), index=False)

    # Final model on all three seasons
    full = prepare_features(df.copy())
    X_full = full[HEADLINE_FEATURES]
    y_full = full[TARGET]

    final_model = lgb.LGBMRegressor(**LGBM_PARAMS)
    final_model.fit(X_full, y_full)
    final_model.booster_.save_model(os.path.join(MODEL_DIR, "headline_final.txt"))

    # Save cross-fit feature importance (average across folds not needed;
    # use final model's importance)
    importance = pd.DataFrame({
        "feature": HEADLINE_FEATURES,
        "gain": final_model.booster_.feature_importance("gain"),
    }).sort_values("gain", ascending=False)
    importance.to_csv(os.path.join(MODEL_DIR, "feature_importance.csv"), index=False)

    print(f"\n  Cross-fit predictions: {len(predictions):,} rows")
    print(f"  Final model saved: {MODEL_DIR}/headline_final.txt")
    return predictions, final_model


if __name__ == "__main__":
    import sys

    print("Loading data...")
    df = load_data()
    print(f"Loaded {len(df):,} rows, seasons: {df['season'].unique()}")

    if len(sys.argv) > 1 and sys.argv[1] == "--gate-b":
        print("\nRunning Gate B: 3-fold season cross-fit...")
        predictions, final_model = train_cross_fit(df)
        print("\nGate B cross-fit complete.")
        print("Next: run build_leaderboard.py, then variants.py")
    else:
        print("\nTraining Gate A model (train: 2022-23 + 2023-24, test: 2024-25)...")
        model, metrics, train_df, test_df = train_gate_a(df)

        print(f"\nGate A Results:")
        print(f"  Train size: {metrics['train_size']:,}")
        print(f"  Test size:  {metrics['test_size']:,}")
        print(f"  Train Poisson deviance: {metrics['train_poisson_deviance']:,.2f}")
        print(f"  Test Poisson deviance:   {metrics['test_poisson_deviance']:,.2f}")
        print(f"  Baseline deviance:       {metrics['baseline_poisson_deviance']:,.2f}")
        print(f"  Lift vs baseline:       {metrics['lift_vs_baseline_pct']:.1f}%")
        print(f"  Best iteration:         {metrics['best_iteration']}")

        print(f"\nFeature importance (gain):")
        imp = pd.read_csv(os.path.join(MODEL_DIR, "feature_importance.csv"))
        for _, row in imp.iterrows():
            print(f"  {row['feature']:35s} {row['gain']:>10,.0f}")

        print(f"\nModel and artifacts saved to {MODEL_DIR}/")