"""backfill_score_margin.py — fill the missing running score margin on shots.

shotchartdetail stamps score_margin only on a subset of shots (~55% land as 0,
which means "not recorded", not "tied"). The cached play-by-play carries the
running score on every scoring event, and shot.event_id maps 1:1 to PBP
actionNumber, so we can reconstruct the margin for every shot.

Conservative: only rows currently stamped 0 are updated (the recorded ones
already match the PBP derivation exactly, verified). Margin is signed by the
shooting team (positive = his team leading), matching the existing convention.
Reproducible from cache; safe to re-run.
"""
import glob
import os
import sqlite3

import pandas as pd

from config import DB_PATH


def margin_at(gid: str) -> dict:
    """Map PBP actionNumber -> (home - away) running score at that event."""
    df = pd.read_parquet(f"cache/pbp/{gid}.parquet").sort_values("actionNumber")
    sh = pd.to_numeric(df["scoreHome"], errors="coerce").ffill().fillna(0)
    sa = pd.to_numeric(df["scoreAway"], errors="coerce").ffill().fillna(0)
    return dict(zip(df["actionNumber"].astype(int), (sh - sa)))


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    shots = pd.read_sql(
        "SELECT rowid, game_id, event_id, home_or_away, score_margin FROM shots",
        conn,
    )
    have = {os.path.basename(f)[:-8] for f in glob.glob("cache/pbp/*.parquet")}

    updates = []
    missing_games = unmatched = 0
    for gid, grp in shots.groupby("game_id"):
        if gid not in have:
            missing_games += 1
            continue
        mm = margin_at(gid)
        for r in grp.itertuples():
            if r.score_margin != 0:        # already recorded, leave it
                continue
            m = mm.get(int(r.event_id))
            if m is None:
                unmatched += 1
                continue
            sign = 1 if r.home_or_away == "home" else -1
            updates.append((int(round(sign * m)), r.rowid))

    conn.executemany("UPDATE shots SET score_margin = ? WHERE rowid = ?", updates)
    conn.commit()

    tot = conn.execute("SELECT COUNT(*) FROM shots").fetchone()[0]
    zero = conn.execute("SELECT COUNT(*) FROM shots WHERE score_margin = 0").fetchone()[0]
    print(f"filled {len(updates):,} shots; games without pbp: {missing_games}; "
          f"unmatched events: {unmatched}")
    print(f"score_margin == 0 now: {zero:,}/{tot:,} = {100 * zero / tot:.1f}% "
          f"(genuine ties + any residual gaps)")
    conn.close()


if __name__ == "__main__":
    main()
