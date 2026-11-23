"""Phase 0 validation gate for site/public/data.json against xfta.db.

Every check prints PASS/FAIL with evidence. Any FAIL exits non-zero.
Run after export_site_data.py.
"""
import json
import math
import random
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
from config import DB_PATH, ERA, EXPORT_DIR  # noqa: E402

JSON_PATH = Path(EXPORT_DIR) / "data.json"

raw_text = JSON_PATH.read_text()
data = json.loads(raw_text)
# Chunked player payloads: stitch back into data["players"] for the checks,
# and include chunk text in the NaN scan.
data["players"] = {}
chunk_sizes = {}
for chunk in sorted(JSON_PATH.parent.glob("players-*.json")):
    season = chunk.stem.replace("players-", "")
    txt = chunk.read_text()
    raw_text += txt
    chunk_sizes[chunk.name] = chunk.stat().st_size / 1e6
    for pid, det in json.loads(txt).items():
        data["players"].setdefault(pid, {"seasons": {}})["seasons"][season] = det
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

failures = []


def report(name: str, ok: bool, detail: str) -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}")
    print(f"       {detail}")
    if not ok:
        failures.append(name)


# ---------------------------------------------------------------- check 1
db_counts = dict(
    cur.execute(
        "SELECT season, COUNT(*) FROM player_season_xfta_poss_lb_clean GROUP BY season"
    ).fetchall()
)
json_counts: dict[str, int] = {}
for row in data["leaderboard"]:
    json_counts[row["season"]] = json_counts.get(row["season"], 0) + 1
report(
    "1. Row counts per season match clean leaderboard table",
    json_counts == db_counts,
    f"db={db_counts} json={json_counts}",
)

# ---------------------------------------------------------------- check 2
lb_by_key = {(r["id"], r["season"]): r for r in data["leaderboard"]}
arc_keys = [
    (int(pid), season)
    for pid, p in data["players"].items()
    for season, det in p["seasons"].items()
    if det["games"]
]
random.seed(7)
sample = random.sample(arc_keys, 10)
lines = []
ok2 = True
for pid, season in sample:
    arc_total = sum(g[0] for g in data["players"][str(pid)]["seasons"][season]["games"])
    fta = lb_by_key[(pid, season)]["fta"]
    match = arc_total == fta
    ok2 &= match
    lines.append(f"{lb_by_key[(pid, season)]['name']} {season}: arc={arc_total} fta={fta}")
report(
    "2. season_arc final cumulative actual == actual_fta (10 sampled players)",
    ok2,
    " | ".join(lines),
)

# ---------------------------------------------------------------- check 3
worst = 0.0
db_ftaoe = {
    (int(pid), season): v
    for pid, season, v in cur.execute(
        "SELECT player_id, season, ftaoe FROM player_season_xfta_poss_lb_clean"
    )
}
worst_db = 0.0
for r in data["leaderboard"]:
    worst = max(worst, abs(r["ftaoe"] - (r["fta"] - r["xfta"])))
    worst_db = max(worst_db, abs(r["ftaoe"] - db_ftaoe[(r["id"], r["season"])]))
report(
    "3. ftaoe == actual_fta - baseline_fta for every row (tol 0.01)",
    worst <= 0.01 and worst_db <= 0.01,
    f"max |ftaoe-(fta-xfta)| in JSON = {worst:.6f}; max |json-db| ftaoe = {worst_db:.6f} "
    f"over {len(data['leaderboard'])} rows",
)

# ---------------------------------------------------------------- check 4
qual = data["meta"]["qualifyPossessions"]
ok4 = True
lines = []
for season in data["meta"]["seasons"]:
    pcts = [
        r["pct"] for r in data["leaderboard"]
        if r["season"] == season and r["poss"] >= qual
    ]
    if not pcts:
        # Thin in-progress season (early weeks): nobody qualified yet.
        lines.append(f"{season}: thin (0 qualified), skipped")
        continue
    if any(p is None for p in pcts):
        ok4 = False
        lines.append(f"{season}: null pct inside qualified pool")
        continue
    lo, hi = min(pcts), max(pcts)
    # The lowest rank in a pool of n sits at about 100/n, so an early season
    # with a handful of qualified players cannot reach ~0 (14 players -> 7.1).
    if lo > max(2, 100 / len(pcts) + 0.5) or hi < 98:
        ok4 = False
    lines.append(f"{season}: pct range {lo}-{hi}, n={len(pcts)}")
unqual_with_pct = sum(
    1 for r in data["leaderboard"] if r["poss"] < qual and r["pct"] is not None
)
nan_in_file = ("NaN" in raw_text) or ("Infinity" in raw_text)
ok4 = ok4 and unqual_with_pct == 0 and not nan_in_file
report(
    "4. Percentiles span ~0-100 in qualified pool; no NaN/Infinity; no pct below threshold",
    ok4,
    f"{' | '.join(lines)} | sub-threshold rows with pct: {unqual_with_pct} | "
    f"NaN/Infinity in file: {nan_in_file}",
)

# ---------------------------------------------------------------- check 5
ok5 = True
worst_sum = 1.0
n_zone_sets = 0
for pid, p in data["players"].items():
    for season, det in p["seasons"].items():
        if not det["zones"]:
            continue
        n_zone_sets += 1
        s = sum(z["share"] for z in det["zones"])
        if abs(s - 1.0) > 0.01:
            ok5 = False
        worst_sum = max(worst_sum, abs(s - 1.0) + 1.0)
# zones must come only from charged FGAs: re-derive totals for 5 samples
zone_sample = random.sample([k for k in arc_keys], 5)
lines = []
for pid, season in zone_sample:
    json_n = sum(z["n"] for z in data["players"][str(pid)]["seasons"][season]["zones"])
    db_n = cur.execute(
        """SELECT COUNT(*) FROM training_fga t
           JOIN shots s ON s.game_id = t.game_id AND s.event_id = t.event_id
           WHERE t.player_id = ? AND t.season = ?
             AND s.shot_zone_basic IS NOT NULL AND s.shot_zone_basic != ''""",
        (pid, season),
    ).fetchone()[0]
    if json_n != db_n:
        ok5 = False
    lines.append(f"{lb_by_key[(pid, season)]['name']} {season}: json={json_n} db={db_n}")
report(
    "5. Zone shares sum to 1±0.01; zone counts re-derived from charged FGAs (5 sampled)",
    ok5,
    f"{n_zone_sets} zone sets, max |sum-1| = {worst_sum - 1.0:.6f} | " + " | ".join(lines),
)

# ---------------------------------------------------------------- check 5b
ok5b = True
worst_key = None
n_checked = 0
for pid, p5 in data["players"].items():
    for season, det in p5["seasons"].items():
        f = det.get("fouls")
        if f is None:
            continue
        n_checked += 1
        fta = lb_by_key[(int(pid), season)]["fta"]
        if f["and1"] + f["sf2"] + f["sf3"] != fta:
            ok5b = False
            worst_key = (pid, season, f, fta)
        if f["located"] > f["and1"]:
            ok5b = False
            worst_key = (pid, season, f, fta)
        if f["zones"]:
            zsum = sum(z["share"] for z in f["zones"])
            if abs(zsum - 1.0) > 0.01:
                ok5b = False
                worst_key = (pid, season, "zone share sum", zsum)
report(
    "5b. Foul ledger identity: and1+sf2+sf3 == actual FTA; located <= and1; "
    "and-1 zone shares sum to 1",
    ok5b and n_checked > 0,
    f"{n_checked} player-seasons checked"
    + (f"; first failure: {worst_key}" if worst_key else "; all exact"),
)

# ---------------------------------------------------------------- check 5c
# Season anchoring: possession-weighted mean FTAOE ~ 0 per season, for both
# the headline and the style-adjusted metric (covered rows only).
ok5c = True
lines = []
for season in data["meta"]["seasons"]:
    rows_s = [r for r in data["leaderboard"] if r["season"] == season]
    poss = sum(r["poss"] for r in rows_s)
    if poss == 0:
        lines.append(f"{season}: thin, skipped")
        continue
    mean_head = sum(r["ftaoe"] for r in rows_s) / poss * 100
    cov = [r for r in rows_s if r.get("sper100") is not None]
    mean_style = (
        sum(r["sper100"] * r["poss"] for r in cov) / sum(r["poss"] for r in cov)
        if cov else 0.0
    )
    if abs(mean_head) > 0.2 or abs(mean_style) > 0.2:
        ok5c = False
    lines.append(f"{season}: head {mean_head:+.3f}, style {mean_style:+.3f}")
report(
    "5c. Anchoring: poss-weighted mean FTAOE per 100 ~ 0 per season (|x|<=0.2)",
    ok5c,
    " | ".join(lines),
)

# ---------------------------------------------------------------- check 5d
ok5d = True
lines = []
# Teams per season from the season's own games (29 until 2004-05), and
# officials only where the feed lists them (none before 2003-04).
_league = conn.execute(
    """SELECT g.season, COUNT(DISTINCT m.home_team_id), AVG(m.n_officials >= 3)
       FROM games g JOIN game_meta m ON m.game_id = g.GAME_ID GROUP BY g.season"""
).fetchall()
n_teams = {s2: n for s2, n, _ in _league}
# a season counts once most of its games name officials (a few late-1990s
# games do, which is not a season of referee data)
with_officials = {s2 for s2, _, share in _league if share > 0.5}
for season, rows in data.get("teams", {}).items():
    if season != data["meta"]["seasons"][-1] and len(rows) != n_teams.get(season):
        ok5d = False
        lines.append(f"{season}: {len(rows)} teams of {n_teams.get(season)}")
        continue
    wd = sum(r["drawn"] * r["poss"] for r in rows) / sum(r["poss"] for r in rows)
    wc = sum(r["conceded"] * r["poss"] for r in rows) / sum(r["poss"] for r in rows)
    if abs(wd) > 0.25 or abs(wc) > 0.25:
        ok5d = False
    lines.append(f"{season}: drawn {wd:+.3f} conceded {wc:+.3f}")
nrefs = {s2: len(v) for s2, v in data.get("referees", {}).items()}
complete = [s2 for s2 in nrefs if s2 != data["meta"]["seasons"][-1] and s2 in with_officials]
if any(nrefs[s2] < 30 for s2 in complete):
    ok5d = False
report(
    "5d. Teams: every team in the season's games, poss-weighted league mean ~0 both sides; refs >= 30 where the feed lists officials",
    ok5d,
    " | ".join(lines) + f" | refs per season: {nrefs}",
)

# ---------------------------------------------------------------- check 6
size_mb = JSON_PATH.stat().st_size / 1e6
# Every page loads the live core on boot, so it stays small. The archive core
# (24 seasons) loads only when a page asks for an archive season, player or
# official, so it gets a looser bound.
core_limit = 6.0 if ERA == "archive" else 2.0
report(
    f"6. Core file < {core_limit:.0f} MB raw (player detail is chunked per season)",
    size_mb < core_limit,
    f"core {size_mb:.2f} MB; chunks: "
    + ", ".join(f"{k} {v:.2f} MB" for k, v in chunk_sizes.items()),
)

# ------------------------------------------------------------- supplementary
missing_pages = [
    (r["id"], r["season"])
    for r in data["leaderboard"]
    if r["poss"] >= qual
    and (
        str(r["id"]) not in data["players"]
        or r["season"] not in data["players"][str(r["id"])]["seasons"]
    )
]
report(
    "S1. Every qualified leaderboard row has a player-page payload",
    not missing_pages,
    f"missing: {missing_pages[:5] if missing_pages else 'none'}",
)
no_team = sum(1 for r in data["leaderboard"] if r["poss"] >= qual and not r["teams"])
report(
    "S2. Every qualified row has at least one derived team",
    no_team == 0,
    f"qualified rows without teams: {no_team}",
)

print()
if failures:
    print(f"GATE FAILED: {len(failures)} check(s): {failures}")
    sys.exit(1)
print("GATE PASSED: all checks green.")
