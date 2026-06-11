"""Pull per-game meta (officials + home/away team ids) from the NBA
liveData CDN boxscore feed. Cached per game; writes the game_meta table.

Usage: python3 scripts/pull_game_meta.py
"""
from __future__ import annotations

import json
import sqlite3
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
from config import DB_PATH, CACHE_DIR  # noqa: E402

CACHE = ROOT / CACHE_DIR / "game_meta"
CACHE.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "Referer": "https://www.nba.com/",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
}
URL = "https://cdn.nba.com/static/json/liveData/boxscore/boxscore_{gid}.json"


def fetch(gid: str) -> dict | None:
    path = CACHE / f"{gid}.json"
    if path.exists():
        return json.loads(path.read_text())
    for attempt in range(3):
        try:
            r = requests.get(URL.format(gid=gid), headers=HEADERS, timeout=30)
            if r.status_code != 200:
                raise RuntimeError(f"http {r.status_code}")
            g = r.json()["game"]
            row = {
                "game_id": gid,
                "home_team_id": g["homeTeam"]["teamId"],
                "away_team_id": g["awayTeam"]["teamId"],
                "officials": [
                    {"id": o["personId"], "name": o["name"]}
                    for o in g.get("officials", [])
                ],
            }
            path.write_text(json.dumps(row))
            time.sleep(0.35)
            return row
        except Exception as e:  # noqa: BLE001
            if attempt == 2:
                print(f"  {gid}: FAILED ({e})")
                return None
            time.sleep(2 * (attempt + 1))
    return None


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


if __name__ == "__main__":
    main()
