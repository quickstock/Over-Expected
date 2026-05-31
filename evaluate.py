"""xFTA Phase 2 — Gate A validation report.

Reads model artifacts from train_model.py and produces:
1. Held-out Poisson deviance + baseline
2. Global calibration plot (PNG)
3. Per-zone calibration
4. Top/bottom-10 shots by xFTA
5. 20-shot spot-check table
6. Feature importance (already saved by train_model.py)
"""

import os
import sqlite3

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from config import DB_PATH, HEADLINE_FEATURES, TARGET

MODEL_DIR = "model_artifacts"


def poisson_deviance(y_true, y_pred):
    y_pred = np.clip(y_pred, 1e-10, None)
    return 2 * np.sum(y_pred - y_true * np.log(y_pred))


def load_test_predictions():
    """Load Gate A test predictions."""
    path = os.path.join(MODEL_DIR, "gate_a_test_full.csv")
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"{path} not found. Run train_model.py first."
        )
    return pd.read_csv(path)


def load_player_names():
    """Load player names from player_season."""
    conn = sqlite3.connect(DB_PATH)
    ps = pd.read_sql("SELECT DISTINCT player_id, player_name FROM player_season", conn)
    conn.close()
    return dict(zip(ps["player_id"], ps["player_name"]))


def report_metrics():
    """1. Held-out Poisson deviance + baseline."""
    import json
    with open(os.path.join(MODEL_DIR, "metrics_gate_a.json")) as f:
        metrics = json.load(f)

    print("=" * 60)
    print("GATE A — VALIDATION REPORT")
    print("=" * 60)
    print()
    print("1. HELD-OUT POISSON DEVIANCE (2024-25)")
    print(f"   Model deviance:    {metrics['test_poisson_deviance']:>12,.2f}")
    print(f"   Baseline deviance:  {metrics['baseline_poisson_deviance']:>12,.2f}")
    print(f"   Baseline (mean FTA per shot): {metrics['baseline_mean_fta']:.6f}")
    print(f"   Lift vs baseline:  {metrics['lift_vs_baseline_pct']:.1f}%")
    print(f"   Train deviance:    {metrics['train_poisson_deviance']:>12,.2f}")
    print(f"   Train size: {metrics['train_size']:,}  Test size: {metrics['test_size']:,}")
    print(f"   Best iteration: {metrics['best_iteration']}")
    return metrics


def calibration_plot(test):
    """2. Global calibration plot — 10 deciles."""
    test = test.dropna(subset=["xfta"]).copy()
    test["decile"] = pd.qcut(test["xfta"], q=10, labels=False, duplicates="drop")

    cal = test.groupby("decile").agg(
        predicted=("xfta", "mean"),
        actual=(TARGET, "mean"),
        count=(TARGET, "count"),
    ).reset_index()

    fig, ax = plt.subplots(figsize=(8, 6))
    ax.scatter(cal["predicted"], cal["actual"], s=cal["count"] / 50, alpha=0.7, color="#E8600A", edgecolors="white", linewidths=0.5)
    max_val = max(cal["predicted"].max(), cal["actual"].max()) * 1.1
    ax.plot([0, max_val], [0, max_val], "--", color="gray", alpha=0.5, label="Perfect calibration")
    ax.set_xlabel("Predicted xFTA", fontsize=12)
    ax.set_ylabel("Actual FTA per shot", fontsize=12)
    ax.set_title("Gate A — Global Calibration (2024-25 held-out)", fontsize=14)
    ax.legend()
    ax.set_xlim(0, max_val)
    ax.set_ylim(0, max_val)
    plt.tight_layout()
    path = os.path.join(MODEL_DIR, "calibration_global.png")
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"\n   Global calibration plot saved: {path}")

    # Print calibration table
    print("\n2. GLOBAL CALIBRATION (10 deciles)")
    print(f"   {'Decile':>6s}  {'Pred xFTA':>10s}  {'Actual FTA':>10s}  {'N':>8s}")
    for _, row in cal.iterrows():
        print(f"   {int(row['decile']):>6d}  {row['predicted']:>10.4f}  {row['actual']:>10.4f}  {int(row['count']):>8d}")
    return cal


def per_zone_calibration(test):
    """3. Per-zone calibration — slope of actual vs predicted within each zone."""
    test = test.dropna(subset=["xfta"]).copy()

    zones = sorted(test["shot_zone_basic"].dropna().unique())
    print("\n3. PER-ZONE CALIBRATION")
    print(f"   {'Zone':>30s}  {'Slope':>6s}  {'Mean Pred':>10s}  {'Mean Actual':>12s}  {'N':>7s}  {'Flag':>6s}")
    print("   " + "-" * 80)

    flagged = []
    for zone in zones:
        z = test[test["shot_zone_basic"] == zone]
        if len(z) < 50:
            continue
        pred_mean = z["xfta"].mean()
        actual_mean = z[TARGET].mean()
        # Slope via simple regression: actual = slope * predicted
        if z["xfta"].std() > 0:
            slope = np.corrcoef(z["xfta"], z[TARGET])[0, 1] * z[TARGET].std() / z["xfta"].std()
        else:
            slope = float("nan")
        flag = " ⚠️" if abs(slope - 1) > 0.15 else ""
        print(f"   {zone:>30s}  {slope:>6.3f}  {pred_mean:>10.4f}  {actual_mean:>12.4f}  {len(z):>7d}  {flag}")
        if abs(slope - 1) > 0.15:
            flagged.append((zone, slope, len(z)))

    if flagged:
        print(f"\n   ⚠️  Zones with calibration slope deviating >0.15 from 1:")
        for zone, slope, n in flagged:
            print(f"      {zone}: slope={slope:.3f} (n={n:,})")
    else:
        print(f"\n   All zones within ±0.15 of slope=1.")

    # Plot per-zone
    fig, ax = plt.subplots(figsize=(10, 6))
    for zone in zones:
        z = test[test["shot_zone_basic"] == zone]
        if len(z) < 50:
            continue
        z = z.copy()
        z["decile"] = pd.qcut(z["xfta"], q=5, labels=False, duplicates="drop")
        zc = z.groupby("decile").agg(pred=("xfta", "mean"), act=(TARGET, "mean")).reset_index()
        ax.scatter(zc["pred"], zc["act"], s=40, alpha=0.7, label=zone)

    max_val = test["xfta"].quantile(0.99) * 1.2
    ax.plot([0, max_val], [0, max_val], "--", color="gray", alpha=0.5)
    ax.set_xlabel("Predicted xFTA")
    ax.set_ylabel("Actual FTA per shot")
    ax.set_title("Per-Zone Calibration (2024-25 held-out)")
    ax.legend(fontsize=8, loc="upper left")
    plt.tight_layout()
    path = os.path.join(MODEL_DIR, "calibration_per_zone.png")
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"\n   Per-zone calibration plot saved: {path}")


def top_bottom_shots(test):
    """4. Top/bottom-10 shots by xFTA."""
    test = test.dropna(subset=["xfta"]).copy()
    player_names = load_player_names()
    test["player_name"] = test["player_id"].map(player_names)

    desc_cols = ["game_id", "event_id", "player_name", "shot_zone_basic", "action_type",
                 "shot_type", "shot_made", "fta_from_shot", "xfta"]

    # Filter to available columns
    avail = [c for c in desc_cols if c in test.columns]

    print("\n4. TOP-10 SHOTS BY xFTA (highest expected foul-drawing)")
    top10 = test.nlargest(10, "xfta")[avail]
    print(top10.to_string(index=False))

    print("\n   BOTTOM-10 SHOTS BY xFTA (lowest expected foul-drawing)")
    bot10 = test.nsmallest(10, "xfta")[avail]
    print(bot10.to_string(index=False))


def spot_check(test):
    """5. 20-shot random spot-check."""
    test = test.dropna(subset=["xfta"]).copy()
    player_names = load_player_names()
    test["player_name"] = test["player_id"].map(player_names)

    sample = test.sample(20, random_state=42)

    cols = ["game_id", "event_id", "player_name", "shot_zone_basic", "action_type",
            "shot_type", "shot_distance", "fta_from_shot", "xfta"]
    avail = [c for c in cols if c in sample.columns]

    print("\n5. 20-SHOT SPOT-CHECK (random sample, seed=42)")
    print(sample[avail].to_string(index=False))


def feature_importance_report():
    """6. Feature importance (read from CSV saved by train_model.py)."""
    path = os.path.join(MODEL_DIR, "feature_importance.csv")
    imp = pd.read_csv(path)
    print("\n6. FEATURE IMPORTANCE (gain-based)")
    print(f"   {'Feature':>35s}  {'Gain':>10s}")
    print("   " + "-" * 48)
    for _, row in imp.iterrows():
        print(f"   {row['feature']:>35s}  {row['gain']:>10,.0f}")


def leaderboard_top30(test):
    """Bonus: held-out season leaderboard top-30."""
    test = test.dropna(subset=["xfta"]).copy()
    player_names = load_player_names()

    lb = test.groupby(["player_id", "season"]).agg(
        fga=("fta_from_shot", "count"),
        actual_fta=("fta_from_shot", "sum"),
        xfta_total=("xfta", "sum"),
    ).reset_index()
    lb["ftaoe"] = lb["actual_fta"] - lb["xfta_total"]
    lb["ftaoe_per_100"] = lb["ftaoe"] / lb["fga"] * 100
    lb["player_name"] = lb["player_id"].map(player_names)
    lb = lb[lb["fga"] >= 100].sort_values("ftaoe_per_100", ascending=False)

    print("\n7. HELD-OUT SEASON LEADERBOARD TOP-30 (min 100 FGA, 2024-25)")
    display = lb.head(30)[["player_name", "fga", "actual_fta", "xfta_total", "ftaoe", "ftaoe_per_100"]]
    print(display.to_string(index=False))


if __name__ == "__main__":
    test = load_test_predictions()

    # Cast categoricals back
    for col in ["shot_zone_basic", "shot_zone_area", "action_type", "shot_type", "home_or_away"]:
        if col in test.columns:
            test[col] = test[col].astype("category")

    metrics = report_metrics()
    calibration_plot(test)
    per_zone_calibration(test)
    top_bottom_shots(test)
    spot_check(test)
    feature_importance_report()
    leaderboard_top30(test)

    print("\n" + "=" * 60)
    print("GATE A COMPLETE — awaiting approval before Gate B")
    print("=" * 60)