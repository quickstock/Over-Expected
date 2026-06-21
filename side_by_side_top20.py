"""Side-by-side: leaky (player_season_xfta_poss_lb) vs clean
(player_season_xfta_poss_lb_clean). Top 20 by clean ftaoe, min 300
possessions. Output to console for the Step 0.4 sign-off.

Bug fix: earlier version was reading xfta_total from the leaky table
while ftaoe/ftaoe_per_100 came from the clean table — producing
non-reconciling numbers (Embiid 646 − 492.3 = 153.7, table showed
+282.3, per_100 16.75 matched the 282.3 not the 153.7). Fixed by
reading ALL clean numbers from the clean table only.
"""
import sqlite3
import pandas as pd
from config import DB_PATH

conn = sqlite3.connect(DB_PATH)

leaky = pd.read_sql("""
    SELECT player_id, season, player_name, position, possessions,
           actual_fta_from_fouls, xfta_total AS xfta_total_leaky,
           ftaoe AS ftaoe_leaky, ftaoe_per_100 AS per_100_leaky,
           ftaoe_rank AS rank_leaky
    FROM player_season_xfta_poss_lb
""", conn)

clean = pd.read_sql("""
    SELECT player_id, season, player_name, position, possessions,
           actual_fta_from_fouls, xfta_total AS xfta_total_clean,
           ftaoe AS ftaoe_clean, ftaoe_per_100 AS per_100_clean,
           ftaoe_rank AS rank_clean
    FROM player_season_xfta_poss_lb_clean
""", conn)

# Merge on (player_id, season) — both tables keyed that way
m = leaky.merge(clean, on=["player_id", "season"], how="inner", suffixes=("", "_dup"))
m = m[m["possessions_x"] >= 300].copy() if "possessions_x" in m.columns else m[m["possessions"] >= 300].copy()
m["rank_delta"] = m["rank_leaky"] - m["rank_clean"]

# Top 20 by clean ftaoe
top = m.sort_values("ftaoe_clean", ascending=False).head(20)

print("=" * 130)
print("TOP 20 BY CLEAN ftaoe  (min 300 possessions)  —  4-feature leak-clean Poisson GLM")
print("=" * 130)
print(f"{'rank':>4}  {'player':22s}  {'season':8s}  {'poss':>5}  "
      f"{'actual':>6}  {'xfta':>7}  {'ftaoe':>7}  {'per100':>7}  "
      f"{'leaky_xfta':>10}  {'leaky_ftaoe':>11}  {'Δrank':>6}")
for i, r in enumerate(top.itertuples(), start=1):
    print(f"{i:>4}  {r.player_name:22s}  {r.season:8s}  "
          f"{int(r.possessions):>5,}  {int(r.actual_fta_from_fouls):>6,}  "
          f"{r.xfta_total_clean:>7.1f}  {r.ftaoe_clean:>+7.1f}  "
          f"{r.per_100_clean:>+7.2f}  "
          f"{r.xfta_total_leaky:>10.1f}  {r.ftaoe_leaky:>+11.1f}  "
          f"{int(r.rank_delta):>+6}")

# Reconciliation check — every row in the table should satisfy
# actual = xfta + ftaoe within rounding. Fail loudly if not.
def _check(df, label):
    err = (df["actual_fta_from_fouls"] - df["xfta_total_clean"] - df["ftaoe_clean"]).abs()
    bad = err[err > 0.5]
    print(f"  {label}: {len(bad)} rows fail reconciliation (max err {err.max():.4f})")
_check(top, "top-20")

# Correlation
print(f"\nSpearman rank correlation (leaky vs clean, ≥300 poss): "
      f"{m[['rank_leaky','rank_clean']].corr(method='spearman').iloc[0,1]:.4f}")

# Biggest movers
biggest_fallers = m.sort_values("rank_delta", ascending=False).head(5)
biggest_risers  = m.sort_values("rank_delta", ascending=False).tail(5)
print("\nBiggest fallers (high leaky rank → lower clean rank):")
for _, r in biggest_fallers.iterrows():
    print(f"  {r['player_name']:22s}  {r['season']:8s}  "
          f"leaky={int(r['rank_leaky']):>4}  clean={int(r['rank_clean']):>4}  "
          f"Δrank={int(r['rank_delta']):+4}  clean_per100={r['per_100_clean']:+.2f}")
print("\nBiggest risers (low leaky rank → higher clean rank):")
for _, r in biggest_risers.iterrows():
    print(f"  {r['player_name']:22s}  {r['season']:8s}  "
          f"leaky={int(r['rank_leaky']):>4}  clean={int(r['rank_clean']):>4}  "
          f"Δrank={int(r['rank_delta']):+4}  clean_per100={r['per_100_clean']:+.2f}")

# Top 20 by leaky — how do they shake out in clean
top_l = m.sort_values("ftaoe_leaky", ascending=False).head(20)
all_clean_ranked = m.sort_values("ftaoe_clean", ascending=False).reset_index(drop=True)
print("\nTop 20 by LEAKY ftaoe — and their clean rank:")
for i, r in enumerate(top_l.itertuples(), start=1):
    pos_in_clean = all_clean_ranked.index[all_clean_ranked["player_id"] == r.player_id]
    pos_in_clean = pos_in_clean[0] + 1 if len(pos_in_clean) else "—"
    print(f"  {i:>3}  {r.player_name:22s}  {r.season:8s}  "
          f"leaky_rank={int(r.rank_leaky):>4}  clean_rank={pos_in_clean}")

# Per-100 distribution
print("\nDistribution of ftaoe_per_100 (≥300 poss):")
print(m[["per_100_leaky", "per_100_clean"]].describe().to_string())

# Mean
print(f"\nMean ftaoe per 100 (should be ~0):")
print(f"  leaky:  {m['per_100_leaky'].mean():+.3f}")
print(f"  clean:  {m['per_100_clean'].mean():+.3f}")

# Top-20 overlap
top20_leaky = set(top_l["player_name"] + "|" + top_l["season"])
top20_clean = set(top["player_name"] + "|" + top["season"])
print(f"\nTop-20 overlap (by name|season): {len(top20_leaky & top20_clean)}/20")

conn.close()
