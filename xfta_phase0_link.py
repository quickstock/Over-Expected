#!/usr/bin/env python3
"""
xFTA - Phase 0: shot-to-free-throw linking (single game)

Goal of this script: prove you can reliably link a shooting foul to
(a) the field-goal attempt it occurred on and (b) the free throws it produced.
This linking is the foundation of the whole xFTA dataset - if it is wrong here,
nothing downstream works.

Scope (deliberate, per the v1 plan):
  - One game only. Eyeball the output before trusting it.
  - Uses play-by-play ONLY (PlayByPlayV2). Shot coordinates / zones come later,
    from shotchartdetail in Phase 1.
  - Production (Phase 1, 3 seasons) should lean on the `pbpstats` library for
    possession parsing. This script links things MANUALLY on purpose, so you
    can see the data shape and the edge cases yourself.

Not handled here (by design - flag for pbpstats / later phases):
  - technical & flagrant free throws (excluded), continuation fouls, double fouls.

Run:  python xfta_phase0_link.py [game_id]
Default game can be changed via DEFAULT_GAME_ID below.
"""

from __future__ import annotations
import sys

try:
    from nba_api.stats.endpoints import playbyplayv2
except ImportError:
    sys.exit("Missing dependency. Run:  pip install nba_api pandas")

import pandas as pd

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
# NBA game-id format: '00' + season-type + 'YY' + 5-digit game number.
# Season type: 1 = preseason, 2 = regular season, 4 = playoffs.
# '0022300001' = 2023-24 regular season, game #1.
DEFAULT_GAME_ID = "0022300001"

# EVENTMSGTYPE codes (PlayByPlayV2)
MADE_SHOT, MISSED_SHOT, FREE_THROW, REBOUND = 1, 2, 3, 4
TURNOVER, FOUL, VIOLATION, SUB, TIMEOUT, JUMP_BALL = 5, 6, 7, 8, 9, 10
PERIOD_END = 13

# Normal free-throw EVENTMSGACTIONTYPE codes: 1-of-1 ... 3-of-3.
# 16 = technical FT (excluded - not a shooting foul we care about).
NORMAL_FT_ACTIONS = {10, 11, 12, 13, 14, 15}

# Events that definitively end a free-throw set when walking the PBP forward.
BALL_LIVE_AGAIN = {MADE_SHOT, MISSED_SHOT, REBOUND, TURNOVER, JUMP_BALL, PERIOD_END}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def describe(row) -> str:
    """Join whichever description fields are populated for an event."""
    parts = [row.get(c) for c in
             ("HOMEDESCRIPTION", "NEUTRALDESCRIPTION", "VISITORDESCRIPTION")]
    return " | ".join(p for p in parts if isinstance(p, str) and p.strip())


def is_three(text: str) -> bool:
    return "3PT" in (text or "")


def expected_fts(made: bool, three: bool) -> int:
    """How many FTs a shooting foul *should* produce, given the shot."""
    if made:
        return 1                       # and-1, whether the make was a 2 or a 3
    return 3 if three else 2


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------
def load_pbp(game_id: str) -> pd.DataFrame:
    print(f"Pulling play-by-play for game {game_id} ...")
    df = playbyplayv2.PlayByPlayV2(game_id=game_id, timeout=60).get_data_frames()[0]
    df = df.sort_values("EVENTNUM").reset_index(drop=True)   # explicit event order
    print(f"  {len(df)} events.\n")
    return df


# ---------------------------------------------------------------------------
# Linking
# ---------------------------------------------------------------------------
def find_linked_fts(df: pd.DataFrame, foul_idx: int, fouled_id) -> list[int]:
    """Walk forward from a foul; collect the free throws it produced.

    Subs / timeouts can appear between FTs of one set, so we skip those and
    only stop once the ball is live again.
    """
    fts: list[int] = []
    period = df.at[foul_idx, "PERIOD"]
    for j in range(foul_idx + 1, min(foul_idx + 25, len(df))):
        ev = df.iloc[j]
        if ev["PERIOD"] != period:
            break
        et = ev["EVENTMSGTYPE"]
        if (et == FREE_THROW
                and ev["PLAYER1_ID"] == fouled_id
                and ev["EVENTMSGACTIONTYPE"] in NORMAL_FT_ACTIONS):
            fts.append(j)
        elif et in (SUB, TIMEOUT):
            continue                   # happens mid-set - keep walking
        elif et in BALL_LIVE_AGAIN:
            break                      # the FT set is definitely over
    return fts


def find_paired_fga(df: pd.DataFrame, foul_idx: int, fouled_id):
    """Find the FGA by the fouled player on the same play (same period+clock)."""
    period = df.at[foul_idx, "PERIOD"]
    clock = df.at[foul_idx, "PCTIMESTRING"]
    best, best_dist = None, 99
    lo, hi = max(0, foul_idx - 6), min(len(df), foul_idx + 7)
    for j in range(lo, hi):
        ev = df.iloc[j]
        if (ev["EVENTMSGTYPE"] in (MADE_SHOT, MISSED_SHOT)
                and ev["PLAYER1_ID"] == fouled_id
                and ev["PERIOD"] == period
                and ev["PCTIMESTRING"] == clock):
            dist = abs(j - foul_idx)
            if dist < best_dist:
                best, best_dist = j, dist
    return best


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main(game_id: str) -> None:
    df = load_pbp(game_id)

    foul_rows = df.index[df["EVENTMSGTYPE"] == FOUL].tolist()
    print(f"{len(foul_rows)} foul events in this game.\n" + "=" * 78)

    shooting = and_ones = flags = 0

    for idx in foul_rows:
        foul = df.iloc[idx]
        fouled_id = foul["PLAYER2_ID"]          # PLAYER2 on a foul = player fouled
        fouled_nm = foul["PLAYER2_NAME"]
        if pd.isna(fouled_id) or fouled_id == 0:
            continue                            # foul with no recorded victim

        fts = find_linked_fts(df, idx, fouled_id)
        fga_idx = find_paired_fga(df, idx, fouled_id)

        # only surface fouls that did something relevant to xFTA
        if not fts and fga_idx is None:
            continue

        when = f"Q{foul['PERIOD']} {foul['PCTIMESTRING']}"

        if fga_idx is not None and fts:
            shot = df.iloc[fga_idx]
            made = shot["EVENTMSGTYPE"] == MADE_SHOT
            three = is_three(describe(shot))
            n, exp = len(fts), expected_fts(made, is_three(describe(shot)))
            kind = "AND-1" if (made and n == 1) else "SHOOTING FOUL"
            if kind == "AND-1":
                and_ones += 1
            shooting += 1
            mism = "" if n == exp else f"   <-- CHECK: expected {exp} FT"
            if mism:
                flags += 1
            print(f"[{kind}]  {when}  fouled: {fouled_nm}")
            print(f"  shot : {describe(shot)}  "
                  f"({'3PT' if three else '2PT'}, {'made' if made else 'missed'})")
            print(f"  FTs  : {n} attempt(s)  ->  FTA_from_shot = {n}{mism}")

        elif fts and fga_idx is None:
            flags += 1
            print(f"[non-shooting / no FGA]  {when}  fouled: {fouled_nm}")
            print(f"  {len(fts)} FT(s) but no field-goal attempt found nearby")
            print( "  -> bonus foul, or fouled before the shot released. "
                  "Excluded from FGA-level target.")

        else:  # FGA found but no FTs linked
            flags += 1
            print(f"[FGA, no FTs]  {when}  fouled: {fouled_nm}  -> inspect manually")

        print("-" * 78)

    print("\nSUMMARY")
    print(f"  shooting fouls linked to a shot : {shooting}")
    print(f"  of which and-1s                 : {and_ones}")
    print(f"  edge cases flagged for eyeball  : {flags}")
    print("\nNext: open NBA.com play-by-play for this game and hand-verify ~10 of")
    print("the rows above. Trust the linker only after that - it is the foundation.")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_GAME_ID)
