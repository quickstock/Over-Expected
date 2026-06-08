"""Per-decile calibration: bucket player-seasons by predicted xFTA, plot
predicted vs actual. Confirms the model is well-calibrated across the range,
not just on the mean.
"""

import sqlite3
import pandas as pd

from config import DB_PATH

conn = sqlite3.connect(DB_PATH)

# Per-player-season aggregates from OOF predictions
ps = pd.read_sql("""
    SELECT
        player_id,
        season,
        SUM(sfta) AS actual_fta,
        SUM(xfta) AS predicted_fta,
        COUNT(*) AS n_poss
    FROM predictions_poss
    GROUP BY player_id, season
    HAVING n_poss >= 100
""", conn)

ps["actual_rate"] = ps["actual_fta"] / ps["n_poss"]
ps["predicted_rate"] = ps["predicted_fta"] / ps["n_poss"]

# Decile cut on predicted_rate
ps["decile"] = pd.qcut(ps["predicted_rate"], 10, labels=False, duplicates="drop") + 1

cal = ps.groupby("decile").agg(
    n_player_seasons=("player_id", "count"),
    mean_predicted=("predicted_rate", "mean"),
    mean_actual=("actual_rate", "mean"),
    total_predicted=("predicted_fta", "sum"),
    total_actual=("actual_fta", "sum"),
    total_poss=("n_poss", "sum"),
).reset_index()

cal["delta_pct"] = (cal["mean_actual"] - cal["mean_predicted"]) / cal["mean_predicted"] * 100

print("Per-decile calibration (player-seasons with ≥100 possessions):")
print()
print(cal.to_string(index=False))
print()

# Total: mean actual rate vs mean predicted rate on this subset
total_pred = cal["total_predicted"].sum()
total_actual = cal["total_actual"].sum()
total_poss = cal["total_poss"].sum()
print(f"Total across all deciles:")
print(f"  mean predicted rate: {total_pred/total_poss:.4f}")
print(f"  mean actual rate:    {total_actual/total_poss:.4f}")
print(f"  delta:               {(total_actual - total_pred)/total_poss*100/((total_pred/total_poss)):.2f}%")
print()

# Diagonality: compute Pearson correlation of mean_predicted vs mean_actual
corr = cal["mean_predicted"].corr(cal["mean_actual"])
print(f"Pearson correlation (mean_predicted vs mean_actual across deciles): {corr:.4f}")

# Linear fit slope — if well-calibrated, slope ≈ 1.0
from numpy import polyfit
slope, intercept = polyfit(cal["mean_predicted"], cal["mean_actual"], 1)
print(f"Linear fit: actual = {slope:.3f} * predicted + {intercept:.4f}")
print(f"  slope (target 1.0): {slope:.3f}")
print(f"  intercept (target 0): {intercept:.4f}")
print()

# Diagonal check: max abs deviation from identity
cal["expected"] = cal["mean_predicted"]
cal["residual"] = cal["mean_actual"] - cal["expected"]
cal["residual_pct"] = cal["residual"] / cal["expected"] * 100
max_dev = cal["residual_pct"].abs().max()
mean_dev = cal["residual_pct"].abs().mean()
print(f"Max |residual %| from identity line: {max_dev:.2f}%")
print(f"Mean |residual %| from identity line: {mean_dev:.2f}%")
print()
print("Residuals by decile:")
print(cal[["decile", "mean_predicted", "mean_actual", "residual", "residual_pct"]].to_string(index=False))

conn.close()
