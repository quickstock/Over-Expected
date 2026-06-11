"""Phase 3 spot check: 5 players, JSON export vs DB. Prints a comparison
table; the UI column gets verified in the browser separately.

Selection: top per100, bottom per100, a median player, a traded player
(2+ teams), and the highest-possession player — all latest season.
"""
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
from config import DB_PATH  # noqa: E402

data = json.loads((ROOT / "site" / "public" / "data.json").read_text())
conn = sqlite3.connect(DB_PATH)

season = data["meta"]["seasons"][-1]
qual = data["meta"]["qualifyPossessions"]
pool = sorted(
    (r for r in data["leaderboard"] if r["season"] == season and r["poss"] >= qual),
    key=lambda r: r["per100"],
)
traded = next((r for r in pool if len(r["teams"]) >= 2), None)
picks = {
    "top per100": pool[-1],
    "bottom per100": pool[0],
    "median": pool[len(pool) // 2],
    "traded": traded,
    "max poss": max(pool, key=lambda r: r["poss"]),
}

print(f"season={season}  (JSON vs DB; tolerance: xfta/ftaoe 0.01)")
all_ok = True
for label, r in picks.items():
    if r is None:
        print(f"{label:>14}: none found")
        continue
    db = conn.execute(
        """SELECT possessions, actual_fta_from_fouls, xfta_total, ftaoe,
                  ftaoe_per_100
           FROM player_season_xfta_poss_lb_clean
           WHERE player_id = ? AND season = ?""",
        (r["id"], season),
    ).fetchone()
    ok = (
        db is not None
        and r["poss"] == db[0]
        and r["fta"] == db[1]
        and abs(r["xfta"] - db[2]) <= 0.01
        and abs(r["ftaoe"] - db[3]) <= 0.01
        and abs(r["per100"] - db[4]) <= 0.01
    )
    all_ok &= ok
    print(
        f"[{'OK' if ok else 'MISMATCH'}] {label:>13}: {r['name']} ({'/'.join(r['teams'])})\n"
        f"     JSON poss={r['poss']} fta={r['fta']} xfta={r['xfta']} "
        f"ftaoe={r['ftaoe']} per100={r['per100']} pct={r['pct']}\n"
        f"     DB   poss={db[0]} fta={db[1]} xfta={round(db[2], 2)} "
        f"ftaoe={round(db[3], 2)} per100={round(db[4], 2)}"
    )
print("SPOT CHECK:", "ALL OK" if all_ok else "MISMATCHES FOUND")
