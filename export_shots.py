"""A sample of each season's shots -> site/public/shots-NBA-{season}.json.

The homepage draws these behind its title: where shots were taken, made or
missed. A fixed-seed sample of SAMPLE half-court shots per season, in
centimetres from the hoop (x across the court, y out from the baseline side),
the same unit the European exports use, so one front-end component draws
every league. Seasons are the exported core's own, so the site never asks
for a season it does not list. Era-aware: OE_ERA=archive writes the
archive's seasons beside its own export.
"""
import json
import sqlite3
import zlib
from pathlib import Path

import numpy as np

from config import DB_PATH, EXPORT_DIR

SAMPLE = 6000
HALF_COURT_M = 14.0
CM_PER_TENTH_FOOT = 3.048  # shot_x/shot_y are tenths of a foot


def sample(season: str, conn) -> dict:
    rows = np.array(conn.execute(
        """SELECT s.shot_x, s.shot_y, s.shot_made FROM shots s
           JOIN games g ON g.GAME_ID = s.game_id WHERE g.season = ?""",
        (season,)).fetchall(), dtype=float)
    rows = rows[rows[:, 1] * CM_PER_TENTH_FOOT < HALF_COURT_M * 100]
    # A season a few games old has fewer shots than the sample: draw them all.
    rng = np.random.default_rng(zlib.crc32(f"NBA{season}".encode()))
    pick = rows[rng.choice(len(rows), min(SAMPLE, len(rows)), replace=False)]
    return {
        "x": np.rint(pick[:, 0] * CM_PER_TENTH_FOOT).astype(int).tolist(),
        "y": np.rint(pick[:, 1] * CM_PER_TENTH_FOOT).astype(int).tolist(),
        "m": "".join("1" if m else "0" for m in pick[:, 2]),
    }


def main() -> None:
    out = Path(EXPORT_DIR)
    seasons = json.loads((out / "data.json").read_text())["meta"]["seasons"]
    conn = sqlite3.connect(DB_PATH)
    for s in seasons:
        (out / f"shots-NBA-{s}.json").write_text(
            json.dumps(sample(s, conn), separators=(",", ":")))
    print(f"shots: {len(seasons)} seasons x {SAMPLE} -> {out}")


if __name__ == "__main__":
    main()
