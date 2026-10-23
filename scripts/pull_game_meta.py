"""Pull per-game meta (officials + home/away team ids) from stats.nba.com's
boxscoresummaryv3. Cached per game; writes the game_meta table.

Source history: the cache was first filled from the cdn.nba.com liveData
boxscore feed, which since October 2026 answers Akamai "Access Denied" to this
machine, a real browser included. boxscoresummaryv3 carries the same fields
(personId, name, team ids) and reproduces cached liveData rows exactly, officials
order included. Not v2: boxscoresummaryv2 returns no officials for late
2025-26 games.

Officials: boxscoresummaryv3 lists none before 2003-04 (probed 2026-10-22), so
archive games before then carry n_officials = 0 and drop out of the referee
views only.

Usage: python3 scripts/pull_game_meta.py              build game_meta from the DB's games
       python3 scripts/pull_game_meta.py --season S   prefetch one season's cache from
                                                     its cached game list (archive pull)
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from pathlib import Path

import pandas as pd
from nba_api.stats.library.http import NBAStatsHTTP

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
from config import DB_PATH, CACHE_DIR  # noqa: E402

CACHE = ROOT / CACHE_DIR / "game_meta"
CACHE.mkdir(parents=True, exist_ok=True)

def fetch(gid: str) -> dict | None:
    path = CACHE / f"{gid}.json"
    if path.exists():
        return json.loads(path.read_text())
    for attempt in range(5):
        try:
            g = NBAStatsHTTP().send_api_request(
                endpoint="boxscoresummaryv3",
                parameters={"GameID": gid, "LeagueID": "00"},
                timeout=30,
            ).get_dict()["boxScoreSummary"]
            row = {
                "game_id": gid,
                "home_team_id": g["homeTeamId"],
                "away_team_id": g["awayTeamId"],
                "officials": [
                    {"id": o["personId"], "name": o["name"]}
                    for o in g.get("officials", [])
                ],
            }
            path.write_text(json.dumps(row))
            time.sleep(0.35)
            return row
        except Exception as e:  # noqa: BLE001
            if attempt == 4:
                print(f"  {gid}: FAILED ({e})")
                return None
            # an empty body is stats.nba.com throttling: back off for longer;
            # and a throttled keep-alive connection keeps hanging while a new
            # one is answered at once, so drop the session either way
            NBAStatsHTTP.set_session(None)
            throttled = isinstance(e, json.JSONDecodeError)
            time.sleep(15 * 2 ** attempt if throttled else 2 * (attempt + 1))
    return None


def prefetch(season: str) -> None:
    gids = pd.read_parquet(ROOT / CACHE_DIR / "seasons" / f"games_{season}.parquet")["GAME_ID"]
    failed = sum(fetch(str(g)) is None for g in gids)
    print(f"{season}: {len(gids)} games, {failed} failed")
    if failed:
        sys.exit(f"{failed} games have no game_meta")


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    gids = [r[0] for r in conn.execute("SELECT GAME_ID FROM games ORDER BY 1")]
    print(f"games: {len(gids)}")
    rows = []
    failed = 0
    for i, gid in enumerate(gids):
        row = fetch(gid)
        if row is None:
            failed += 1
            continue
        offs = row["officials"][:3] + [{"id": None, "name": None}] * 3
        rows.append(
            (
                row["game_id"], row["home_team_id"], row["away_team_id"],
                offs[0]["id"], offs[0]["name"],
                offs[1]["id"], offs[1]["name"],
                offs[2]["id"], offs[2]["name"],
                len(row["officials"]),
            )
        )
        if (i + 1) % 250 == 0:
            print(f"  {i + 1}/{len(gids)} ({failed} failed)")
    print(f"done: {len(rows)} rows, {failed} failed")

    conn.execute("DROP TABLE IF EXISTS game_meta")
    conn.execute(
        """CREATE TABLE game_meta (
             game_id TEXT PRIMARY KEY, home_team_id INTEGER,
             away_team_id INTEGER,
             ref1_id INTEGER, ref1_name TEXT,
             ref2_id INTEGER, ref2_name TEXT,
             ref3_id INTEGER, ref3_name TEXT,
             n_officials INTEGER)"""
    )
    conn.executemany(
        "INSERT INTO game_meta VALUES (?,?,?,?,?,?,?,?,?,?)", rows
    )
    conn.commit()
    n3 = conn.execute(
        "SELECT COUNT(*) FROM game_meta WHERE n_officials >= 3"
    ).fetchone()[0]
    print(f"game_meta written; {n3}/{len(rows)} games with 3+ officials")
    # shot_value.py inner-joins game_meta, so a game missing here silently
    # drops out of the shot-value suite. Fail loudly instead.
    if failed:
        sys.exit(f"{failed} games have no game_meta")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--season")
    args = ap.parse_args()
    if args.season:
        prefetch(args.season)
    else:
        main()
