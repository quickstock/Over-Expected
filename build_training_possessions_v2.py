"""Build the possession-grain training table: training_possessions_v2.

Walks the SAME possession boundaries as build_possessions_v3 (so the
target is identical to player_season_xfta_poss) and attaches the locked
context-only feature set per possession. No player identity, no derived
foul/FT signal — only what was true at the moment the possession ended.

Target: sfta (integer 0/1/2/3) — the count of shooting-foul / and-1 FTs
        awarded in this possession.

Features (locked design — context only):
  - shot_distance    (terminal FG distance in feet, 0 if non-FG-ending)
  - shot_zone_basic  (pbpstats shot_type: AtRim/ShortMidRange/LongMidRange/Arc3/Corner3/None)
  - action_type      (terminal action: Made Shot / Missed Shot / Turnover / other)
  - shot_type        (2pt / 3pt / unknown)
  - period           (1-7)
  - seconds_remaining_in_period  (terminal event clock)
  - score_margin     (home - away at terminal event; positive = home lead)
  - in_bonus         (period >= 4 proxy — full V3 PBP doesn't carry team bonus
                      state; proxy is the standard cutoff used in research
                      for the last 2 minutes of Q4/OT. Conservative.)
  - home_or_away     (terminal event's `location` field: h/v)
"""
import sys
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, "/Users/kevin/Library/Python/3.9/lib/python/site-packages")

from build_possessions_v3 import build_events
from pbpstats.data_loader.nba_possession_loader import NbaPossessionLoader
from pbpstats.resources.enhanced_pbp import (
    FieldGoal as FG,
    FreeThrow as FTBase,
    Turnover as TV,
    Rebound as RB,
)
from config import DB_PATH

CATEGORICAL = [
    "shot_zone_basic",
    "action_type",
    "shot_type",
    "home_or_away",
]


def safe_int(x, default=0):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return default
    try:
        return int(x)
    except (ValueError, TypeError):
        return default


def derive_features(p_events):
    """Pick the terminal event's context for one possession.

    Terminal = last FieldGoal in the possession. If none (turnover-only
    or pure FT trip), fall back to the last Turnover, then the last event
    of any kind.
    """
    last_fg = None
    last_tv = None
    last_e = p_events[-1] if p_events else None
    for e in p_events:
        if isinstance(e, FG):
            last_fg = e
        elif isinstance(e, TV):
            last_tv = e

    terminal = last_fg or last_tv or last_e
    if terminal is None:
        return None

    if isinstance(terminal, FG):
        dist = getattr(terminal, "distance", None)
        zone = getattr(terminal, "shot_type", None) or "unknown"
        action_type = "made" if terminal.is_made else "missed"
        shot_type = f"{getattr(terminal, 'shot_value', 2)}pt"
    elif isinstance(terminal, TV):
        dist = None
        zone = "unknown"
        action_type = "turnover"
        shot_type = "unknown"
    else:
        dist = None
        zone = "unknown"
        action_type = "other"
        shot_type = "unknown"

    period = safe_int(getattr(terminal, "period", None))
    secs_remaining = getattr(terminal, "seconds_remaining", None)

    home_score = safe_int(getattr(terminal, "home_score", None), default=None)
    away_score = safe_int(getattr(terminal, "away_score", None), default=None)
    if home_score is None or away_score is None:
        score_margin = None
    else:
        score_margin = home_score - away_score

    location = getattr(terminal, "location", None)
    if location == "h":
        home_or_away = "home"
    elif location == "v":
        home_or_away = "away"
    else:
        home_or_away = "unknown"

    in_bonus = 1 if period and period >= 4 else 0

    return {
        "shot_distance": dist if dist is not None else np.nan,
        "shot_zone_basic": zone,
        "action_type": action_type,
        "shot_type": shot_type,
        "period": period if period else np.nan,
        "seconds_remaining_in_period": secs_remaining if secs_remaining is not None else np.nan,
        "score_margin": score_margin if score_margin is not None else np.nan,
        "in_bonus": in_bonus,
        "home_or_away": home_or_away,
    }


def main():
    pbp_dir = Path("cache/pbp")
    files = sorted(pbp_dir.glob("*.parquet"))
    print(f"Walking {len(files)} games for possession features...")

    rows = []
    for i, fp in enumerate(files):
        df = pd.read_parquet(fp)
        gid = fp.stem
        events = build_events(df, gid)
        if not events:
            continue

        class _L(NbaPossessionLoader):
            def __init__(self, evs):
                self.events = evs

        groups = _L(events)._split_events_by_possession()

        for j, g in enumerate(groups):
            if not g:
                continue
            feats = derive_features(g)
            if feats is None:
                continue
            feats["game_id"] = gid
            feats["possession_number"] = j + 1
            rows.append(feats)

        if (i + 1) % 500 == 0:
            print(f"  {i+1}/{len(files)} games, {len(rows):,} possessions")

    print(f"\nTotal possession rows: {len(rows):,}")
    df = pd.DataFrame(rows)

    # Persist raw feature rows so re-runs don't re-walk 3,690 games
    cache_dir = Path("cache/training")
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_fp = cache_dir / "possession_features_raw.parquet"
    df.to_parquet(cache_fp, index=False)
    print(f"Cached raw features: {cache_fp}")

    conn = sqlite3.connect(DB_PATH)
    games = pd.read_sql("SELECT GAME_ID, season FROM games", conn)
    conn.close()
    games = games.rename(columns={"GAME_ID": "game_id"})
    df = df.merge(games, on="game_id", how="left")
    print(f"After season join: {len(df):,} (rows without season: {df['season'].isna().sum()})")

    df = df.dropna(subset=["season"])

    df["sfta"] = 0  # placeholder; will be filled in by joining to possessions table
    conn = sqlite3.connect(DB_PATH)
    poss = pd.read_sql(
        "SELECT game_id, possession_number, sfta AS sfta_target, finisher_player_id "
        "FROM possessions",
        conn,
    )
    conn.close()
    df = df.merge(
        poss,
        on=["game_id", "possession_number"],
        how="left",
    )
    df["sfta"] = df["sfta_target"].fillna(0).astype(int)
    df = df.drop(columns=["sfta_target"])
    print(f"After sfta join: {len(df):,}; mean sfta={df['sfta'].mean():.4f}, "
          f"share>0={ (df['sfta']>0).mean()*100:.2f}%")

    conn = sqlite3.connect(DB_PATH)
    conn.execute("DROP TABLE IF EXISTS training_possessions_v2")
    df.to_sql("training_possessions_v2", conn, if_exists="replace", index=False)
    conn.execute(
        "CREATE INDEX idx_tpv2_season ON training_possessions_v2(season)"
    )
    conn.execute(
        "CREATE INDEX idx_tpv2_game ON training_possessions_v2(game_id)"
    )
    conn.commit()
    conn.close()
    print(f"\nWrote training_possessions_v2 ({len(df):,} rows).")


if __name__ == "__main__":
    main()
