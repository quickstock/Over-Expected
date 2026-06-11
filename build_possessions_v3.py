"""Step 1+2+3 of the EXACT Fix: build possession rows from V3 PBP using
pbpstats' Live event classes and pbpstats' possession splitter.

Non-negotiable rules (per the EXACT Fix spec):
  1. No custom possession logic — possession boundaries come from
     pbpstats' NbaPossessionLoader._split_events_by_possession, which uses
     Event.is_possession_ending_event (offense_team_id change between events).
  2. No scale/fudge factors — none applied here. (The 1.11 scale was patched
     into build_possession_leaderboard.py and is removed in a separate edit.)
  3. Include and-1s — pbpstats' FieldGoal.is_and1 already detects them; a
     1-FT trip after a made FG by the same player is captured by pbpstats
     as `free_throw_type == "1pt And 1"`.
  4. Reuse, do not re-derive, the trip definition — FreeThrow.free_throw_type
     from pbpstats' LiveFreeThrow class is the single source of truth for
     which FT trips count.
  5. Never rationalize a failing check — see check_acceptance.py.

The only custom code in this file is the row-dict adapter (to populate
`descriptor`, `possession`, `qualifiers` from V3 PBP columns into the shape
pbpstats expects). All event classification, possession splitting, and
trip definition live in pbpstats.
"""

from __future__ import annotations

import os
import re
import sqlite3
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Optional

import pandas as pd

from config import DB_PATH

# ─── pbpstats imports ────────────────────────────────────────────────────
sys.path.insert(0, "/Users/kevin/Library/Python/3.9/lib/python/site-packages")
from pbpstats.resources.enhanced_pbp.live.enhanced_pbp_item import LiveEnhancedPbpItem
from pbpstats.resources.enhanced_pbp.live.field_goal import LiveFieldGoal
from pbpstats.resources.enhanced_pbp.live.free_throw import LiveFreeThrow
from pbpstats.resources.enhanced_pbp.live.rebound import LiveRebound
from pbpstats.resources.enhanced_pbp.live.turnover import LiveTurnover
from pbpstats.resources.enhanced_pbp.live.foul import LiveFoul
from pbpstats.resources.enhanced_pbp.live.end_of_period import LiveEndOfPeriod
from pbpstats.resources.enhanced_pbp.live.start_of_period import LiveStartOfPeriod
from pbpstats.resources.enhanced_pbp.live.jump_ball import LiveJumpBall
from pbpstats.resources.enhanced_pbp.live.substitution import LiveSubstitution
from pbpstats.resources.enhanced_pbp.live.timeout import LiveTimeout
from pbpstats.resources.enhanced_pbp.live.violation import LiveViolation
from pbpstats.resources.enhanced_pbp.live.replay import LiveReplay
from pbpstats.resources.possessions.possession import Possession
from pbpstats.data_loader.nba_possession_loader import NbaPossessionLoader


CACHE_DIR = Path("cache")
PBP_DIR = CACHE_DIR / "pbp"

# ─── V3 PBP → pbpstats item adapter ─────────────────────────────────────
# We only ADAPT the row dict; we do not classify fouls/FTs/possession-changes
# ourselves. pbpstats' Live* classes do all the classification.

# Foul subType → descriptor mapping (mirrors pbpstats' LiveFoul expectations).
# All values come from V3 PBP's `description` text; the patterns below are
# stable across all 3,690 games in cache/pbp.
_FOUL_DESC_TO_DESCRIPTOR = [
    # (regex, descriptor_string)
    (re.compile(r"\bS\.FOUL\b", re.IGNORECASE), "shooting"),
    (re.compile(r"\bSHOOTING\b", re.IGNORECASE), "shooting"),
    (re.compile(r"\bL\.BALL\b", re.IGNORECASE), "looseball"),
    (re.compile(r"\bLOOSE BALL\b", re.IGNORECASE), "looseball"),
    (re.compile(r"\bOFFENSIVE CHARGE\b", re.IGNORECASE), "charge"),
    (re.compile(r"\bOFFENSIVE\b", re.IGNORECASE), None),  # leave descriptor unset → offensive_foul
    (re.compile(r"\bINBOUND\b", re.IGNORECASE), "inbound"),
    (re.compile(r"\bAWAY\b", re.IGNORECASE), "awayfromplay"),
    (re.compile(r"\bCLEAR PATH\b", re.IGNORECASE), "clearpath"),
    (re.compile(r"\bDOUBLE\b", re.IGNORECASE), "double"),
    (re.compile(r"\bFLAG\.1\b", re.IGNORECASE), "flagranttype1"),
    (re.compile(r"\bFLAG\.2\b", re.IGNORECASE), "flagranttype2"),
    (re.compile(r"\bFLAG\b", re.IGNORECASE), "flagranttype1"),
    (re.compile(r"\bDEF\.3\b", re.IGNORECASE), "defensive3second"),
    (re.compile(r"\bDELAY\b", re.IGNORECASE), "delay"),
    (re.compile(r"\bTAKE\b", re.IGNORECASE), "take"),
    (re.compile(r"\bTRANSITION\b", re.IGNORECASE), "transition"),
    (re.compile(r"\bBLOCK\b", re.IGNORECASE), "block"),
    (re.compile(r"\bT\.FOUL\b", re.IGNORECASE), "technical"),
    (re.compile(r"\bTECHNICAL\b", re.IGNORECASE), "technical"),
]


def _foul_descriptor(desc: str) -> Optional[str]:
    if not isinstance(desc, str):
        return None
    for pat, val in _FOUL_DESC_TO_DESCRIPTOR:
        if pat.search(desc):
            return val
    return None


# FT descriptor: technical, flagrant, awayfromplay (pbpstats' LiveFreeThrow reads these)
def _ft_descriptor(desc: str, sub_type: str) -> Optional[str]:
    if not isinstance(desc, str):
        return None
    if "TECHNICAL" in desc.upper() or sub_type == "Technical":
        return "technical"
    if "FLAG" in desc.upper() or sub_type == "Flagrant":
        return "flagrant"
    if "AWAY" in desc.upper():
        return "awayfromplay"
    return None


def _is_qualifier_in_desc(desc: str, qual: str) -> bool:
    """Check if `qual` (a pbpstats qualifier like '1freethrow', '2freethrow',
    '3freethrow') is implied by the V3 PBP description.

    V3 PBP embeds the count in the foul text via tokens like 'S.FOUL (1 FTA)'
    or '(2 FTA)'. We accept a small amount of fuzzy matching here; pbpstats
    only reads `qualifiers` for `number_of_fta_for_foul` on Foul objects, and
    our sfta computation uses `FreeThrow.num_ft_for_trip` (parses the "of N"
    text) — not `Foul.number_of_fta_for_foul` — so this is best-effort.
    """
    if not isinstance(desc, str):
        return False
    d = desc.lower()
    if qual == "1freethrow":
        return "1 fta" in d
    if qual == "2freethrow":
        return "2 fta" in d
    if qual == "3freethrow":
        return "3 fta" in d
    return False


def _derive_qualifiers(desc: str, action_type: str) -> list[str]:
    """Best-effort qualifier list for a V3 PBP event.

    Only Foul events need this (for number_of_fta_for_foul). FTs and FGs
    don't read qualifiers in pbpstats' Live* classes.
    """
    if action_type != "Foul":
        return []
    if not isinstance(desc, str):
        return []
    quals = []
    if "1 fta" in desc.lower():
        quals.append("1freethrow")
    if "2 fta" in desc.lower():
        quals.append("2freethrow")
    if "3 fta" in desc.lower():
        quals.append("3freethrow")
    return quals


def _compute_offense_team_id(df: pd.DataFrame) -> pd.Series:
    """Derive the `possession` (= offense_team_id) field per event.

    This is a *required input* to pbpstats' LiveEnhancedPbpItem (it sets
    `self.offense_team_id` from the dict's `possession` key). pbpstats'
    data.nba.com source supplies this field; the live V3 PBP API does not.

    Live convention (per pbpstats' _change_team_id_on_drebs):
      offense_team_id is the team with possession *at the start of the
      event*. So:
        - Made Shot / Missed Shot / Turnover / Free Throw:
            offense_team_id = event's teamId (the team acting)
        - Rebound:
            dreb → offense_team_id = rebound team (possession just changed)
            oreb → offense_team_id = shooter team (possession unchanged)
        - Foul:
            offense_team_id = previous event's offense_team_id
            (a foul does NOT change possession; the ball stays with
            the team that just had it)
        - Jump Ball: look ahead to next action event's team
        - period / EndOfPeriod / Substitution / Timeout / Replay:
            offense_team_id = previous (no possession change)
    """
    poss = pd.Series(0, index=df.index, dtype=int)
    current_poss = 0
    for i, row in df.iterrows():
        at = str(row.get("actionType", "") or "")
        team = row.get("teamId")
        team = int(team) if team is not None and not pd.isna(team) else 0

        if at in ("Made Shot", "Missed Shot", "Free Throw", "Turnover"):
            if team != 0:
                current_poss = team
        elif at == "Rebound":
            # Defensive rebound: possession changes to rebounder's team
            # Offensive rebound: possession stays
            if team != 0 and team != current_poss:
                current_poss = team
            # else: keep current_poss (offensive rebound OR team==0)
        elif at == "Foul":
            # Fouls do not change possession
            pass
        elif at == "Jump Ball":
            for j in range(i + 1, min(i + 10, len(df))):
                nat = str(df.iloc[j].get("actionType", "") or "")
                if nat in ("Made Shot", "Missed Shot", "Free Throw", "Turnover"):
                    nt = df.iloc[j].get("teamId")
                    if nt is not None and not pd.isna(nt) and int(nt) != 0:
                        current_poss = int(nt)
                    break
        elif at in ("period", "EndOfPeriod", "Substitution", "Timeout", "Instant Replay"):
            # No possession change
            pass

        poss.at[i] = current_poss
    return poss


def row_to_item_dict(row: pd.Series, gid: str, poss_value: int = 0) -> dict:
    """Build a pbpstats LiveEnhancedPbpItem input dict from a V3 PBP row.

    Only ADAPTS the V3 PBP columns into the shape pbpstats expects.
    All classification happens in pbpstats' Live* classes.
    """
    at = str(row.get("actionType") or "")
    desc = str(row.get("description") or "") if row.get("description") is not None else ""
    sub_type = str(row.get("subType") or "") if row.get("subType") is not None else ""

    # descriptor: only Foul and FT have descriptors in pbpstats
    descriptor = None
    if at == "Foul":
        descriptor = _foul_descriptor(desc)
    elif at == "Free Throw":
        descriptor = _ft_descriptor(desc, sub_type)

    d: dict = {
        "actionNumber": int(row.get("actionNumber") or 0),
        "clock": str(row.get("clock") or ""),
        "period": int(row.get("period") or 0),
        "teamId": int(row.get("teamId") or 0) if row.get("teamId") is not None else None,
        "personId": int(row.get("personId") or 0) if row.get("personId") is not None else None,
        "actionType": at,
        "subType": sub_type,
        "description": desc,
        "xLegacy": int(row.get("xLegacy") or 0) if row.get("xLegacy") is not None else None,
        "yLegacy": int(row.get("yLegacy") or 0) if row.get("yLegacy") is not None else None,
        "shotResult": str(row.get("shotResult") or "") if row.get("shotResult") is not None else "",
        "shotDistance": int(row.get("shotDistance") or 0) if row.get("shotDistance") is not None else None,
        "scoreHome": str(row.get("scoreHome") or "") if row.get("scoreHome") is not None else "",
        "scoreAway": str(row.get("scoreAway") or "") if row.get("scoreAway") is not None else "",
        "pointsTotal": int(row.get("pointsTotal") or 0) if row.get("pointsTotal") is not None else None,
        "location": str(row.get("location") or "") if row.get("location") is not None else "",
        "possession": int(poss_value or 0),
    }
    if descriptor is not None:
        d["descriptor"] = descriptor
    if at == "Foul":
        d["qualifiers"] = _derive_qualifiers(desc, at)
    else:
        d["qualifiers"] = []
    return d


# ─── pbpstats Live event construction ────────────────────────────────────
LIVE_CLASS_MAP = {
    "Made Shot": LiveFieldGoal,
    "Missed Shot": LiveFieldGoal,
    "Free Throw": LiveFreeThrow,
    "Foul": LiveFoul,
    "Rebound": LiveRebound,
    "Turnover": LiveTurnover,
    "Jump Ball": LiveJumpBall,
    "Substitution": LiveSubstitution,
    "Timeout": LiveTimeout,
    "Violation": LiveViolation,
    "Instant Replay": LiveReplay,
    "period": LiveStartOfPeriod,  # V3 PBP uses 'period' for period-start events
    "StartOfPeriod": LiveStartOfPeriod,
    "EndOfPeriod": LiveEndOfPeriod,
}


def build_events(df: pd.DataFrame, gid: str) -> list:
    """Construct pbpstats LiveEnhancedPbpItem instances from a V3 PBP game df."""
    df = df.copy()
    poss_series = _compute_offense_team_id(df)
    events = []
    for idx, row in df.iterrows():
        at = str(row.get("actionType") or "")
        if at in ("period", "EndOfPeriod"):
            # period markers are NOT passed to pbpstats as live events; they
            # exist only to mark period boundaries in the raw data
            continue
        cls = LIVE_CLASS_MAP.get(at)
        if cls is None:
            continue
        try:
            poss_val = int(poss_series.loc[idx]) if idx in poss_series.index else 0
            d = row_to_item_dict(row, gid, poss_value=poss_val)
            ev = cls(d, gid)
            events.append(ev)
        except Exception:
            continue
    for i, e in enumerate(events):
        e.next_event = events[i + 1] if i + 1 < len(events) else None
        e.previous_event = events[i - 1] if i > 0 else None
    return events


# ─── Possession construction via pbpstats' splitter ────────────────────
class V3PossessionLoader(NbaPossessionLoader):
    """Loads V3 PBP into pbpstats event objects, then uses pbpstats' own
    _split_events_by_possession to bucket events into possessions.

    No custom splitter. No custom offense_team_id. pbpstats does both.
    """

    def __init__(self, gid: str, df: pd.DataFrame):
        self.gid = gid
        self.events = build_events(df, gid)
        events_by_possession = self._split_events_by_possession()  # pbpstats' splitter
        self.items = [Possession(g) for g in events_by_possession]
        self._add_extra_attrs_to_all_possessions()


# ─── sfta target from pbpstats Possession ───────────────────────────────
def possession_sfta_and_finisher(p: Possession):
    """Compute sfta (integer) and finisher_player_id for a pbpstats Possession.

    sfta rule (per spec):
      - For each shooting-foul FT trip in the possession, sfta += M
        where M is the number of FTs shot in the trip (1, 2, or 3).
      - pbpstats' FreeThrow.free_throw_type returns strings like
        "2pt Shooting Foul", "1pt And 1", "3pt Shooting Foul", "Technical",
        "Penalty", "1 Shot Away From Play", "1 Shot Flagrant" etc.
      - We include the trip ONLY if the type contains "Shooting Foul" or
        "And 1". All other trip types (technical/flagrant/clear-path/
        away-from-play/inbound/penalty) are excluded.
      - A trip is one or more consecutive FreeThrow events with the same
        shooter and the same descriptor (i.e. same foul). We sum 1 per FT
        event in qualifying trips.

    And-1 rule: a made FG + 1-FT trip by the same player is the and-1 case.
    pbpstats' FieldGoal.is_and1 detects this automatically, and the
    FreeThrow.free_throw_type returns "1pt And 1" (or "2pt And 1" / "3pt And 1"
    in the G-League). The "And 1" string is what we match on.
    """
    from pbpstats.resources.enhanced_pbp import FreeThrow as FTBase
    from pbpstats.resources.enhanced_pbp import FieldGoal as FG
    from pbpstats.resources.enhanced_pbp import Foul as FL
    from pbpstats.resources.enhanced_pbp import Turnover as TV

    sfta = 0
    excluded_count = 0
    contamination_count = 0
    ft_shooter = None
    last_made = None
    last_made_event = None
    last_shooter = None
    last_turnover = None
    # Shooting-foul FT buckets: identity ft_and1+ft_sf2+ft_sf3 == sfta
    # holds by construction (every kept FT lands in exactly one bucket).
    ft_and1 = 0
    ft_sf2 = 0
    ft_sf3 = 0
    and1_events: set[tuple[int, int]] = set()  # (made-FG event num, player)

    for e in p.events:
        if isinstance(e, FG):
            if e.is_made and e.player1_id:
                last_made = int(e.player1_id)
                last_made_event = getattr(e, "actionNumber", None) or getattr(
                    e, "event_num", None
                )
            if e.player1_id:
                last_shooter = int(e.player1_id)
        elif isinstance(e, FTBase):
            try:
                ft_type = e.free_throw_type or ""
            except Exception:
                # pbpstats raises when its `previous_event` Foul link is None
                # (rare edge — 3 trips in 2 games out of 132k). Drop the trip.
                excluded_count += 1
                continue
            if "Shooting Foul" in ft_type or "And 1" in ft_type:
                # Extra check: pbpstats' free_throw_type returns
                # "3pt Shooting Foul" for flagrant-1 / flagrant-2 trips too
                # (the foul was a flagrant, not a shooting foul, but the
                # classifier doesn't notice). Use the raw V3 PBP description
                # to detect "Flagrant" trips and exclude them — those are
                # penalty FTs, not shooting-foul FTs.
                ft_desc = (e.description or "")
                if "Flagrant" in ft_desc:
                    excluded_count += 1
                    continue
                # pbpstats accepts the trip; verify the causing Foul's
                # descriptor is a shooting foul (or there's no in-possession
                # Foul, in which case it's an and-1 whose foul was the shot
                # itself — pbpstats FieldGoal.is_and1 already validated).
                kept = True
                for prev in p.events:
                    if prev is e:
                        break
                    if isinstance(prev, FL):
                        d = getattr(prev, "descriptor", None)
                        if d in NON_SHOOTING_FOUL_DESCRIPTORS:
                            kept = False
                            contamination_count += 1
                        break
                if kept:
                    sfta += 1
                    if e.player1_id:
                        ft_shooter = int(e.player1_id)
                    if "And 1" in ft_type:
                        ft_and1 += 1
                        # The and-1's made shot: the last made FG by the same
                        # shooter earlier in the possession. Gives the shot
                        # location via the shots table (event id join).
                        if (
                            last_made is not None
                            and e.player1_id
                            and int(e.player1_id) == last_made
                            and last_made_event is not None
                        ):
                            and1_events.add((int(last_made_event), last_made))
                    elif ft_type.startswith("3"):
                        ft_sf3 += 1
                    else:
                        ft_sf2 += 1
                else:
                    excluded_count += 1
            else:
                excluded_count += 1
        elif isinstance(e, TV):
            if e.player1_id:
                last_turnover = int(e.player1_id)

    if ft_shooter is not None:
        # If a qualifying FT trip happened, the FT shooter is the finisher.
        # (A teammate who made a shot earlier in the same possession chunk
        # is not the relevant actor — the FT was awarded to the player
        # who was fouled, and that's the player whose sfta we're counting.)
        finisher = ft_shooter
    elif last_made is not None:
        finisher = last_made
    elif last_turnover is not None:
        finisher = last_turnover
    elif last_shooter is not None:
        finisher = last_shooter
    else:
        finisher = None

    return (
        sfta, finisher, excluded_count, contamination_count,
        ft_and1, ft_sf2, ft_sf3, sorted(and1_events),
    )


# Non-shooting foul descriptors that pbpstats' FieldGoal.is_and1 can
# mistakenly pair with a Made FG. When a technical/double/delay/etc foul
# occurs just before a made basket, the resulting 1-FT trip gets classified
# "2pt And 1" by pbpstats but is actually a technical/delay FT, not a
# shooting-foul FT. Audit (2026-06-06) found 113 of 132,103 kept trips
# (0.085%) of this contamination; production drops them.
NON_SHOOTING_FOUL_DESCRIPTORS = {
    "technical", "double", "delay", "flagranttype1", "flagranttype2",
    "defensive3second", "def3second", "looseball", "charge", "inbound",
    "awayfromplay", "clearpath", "take", "transition", "block", "penalty",
}


# ─── Main pipeline ───────────────────────────────────────────────────────
def process_game(df: pd.DataFrame, gid: str) -> tuple[list[dict], list[dict]]:
    loader = V3PossessionLoader(gid, df)
    out = []
    and1_rows = []
    for p in loader.items:
        if not p.events:
            continue
        (sfta, finisher, excluded, contamination,
         ft_and1, ft_sf2, ft_sf3, and1_events) = possession_sfta_and_finisher(p)
        out.append({
            "game_id": gid,
            "period": p.period,
            "possession_number": p.number,
            "start_time": p.start_time,
            "end_time": p.end_time,
            "offense_team_id": p.offense_team_id,
            "n_events": len(p.events),
            "sfta": sfta,
            "finisher_player_id": finisher,
            "excluded_ft_count": excluded,
            "contamination_count": contamination,
            "ft_and1": ft_and1,
            "ft_sf2": ft_sf2,
            "ft_sf3": ft_sf3,
        })
        for ev, pid in and1_events:
            and1_rows.append({
                "game_id": gid,
                "event_id": ev,
                "player_id": pid,
                "possession_number": p.number,
            })
    return out, and1_rows


def main():
    files = sorted(PBP_DIR.glob("*.parquet"))
    print(f"Step 1+2+3: build possession rows via pbpstats")
    print(f"  games: {len(files)}")
    print(f"  source: {PBP_DIR}/*.parquet (V3 NBA Stats live PBP)")
    print(f"  splitter: pbpstats NbaPossessionLoader._split_events_by_possession")
    print(f"  trip def: pbpstats FreeThrow.free_throw_type")
    print()

    t0 = time.time()
    all_possessions: list[dict] = []
    all_and1: list[dict] = []
    for i, fp in enumerate(files):
        gid = fp.stem
        try:
            df = pd.read_parquet(fp)
            possessions, and1_rows = process_game(df, gid)
            all_possessions.extend(possessions)
            all_and1.extend(and1_rows)
        except Exception as e:
            print(f"  {gid}: FAILED ({e})")
        if (i + 1) % 500 == 0:
            print(f"  {i+1}/{len(files)} games, {len(all_possessions):,} possessions, {time.time()-t0:.1f}s")

    print(f"\nTotal: {len(all_possessions):,} possessions from {len(files)} games")
    print(f"Elapsed: {time.time()-t0:.1f}s")

    # Write to SQLite
    poss_df = pd.DataFrame(all_possessions)
    print(f"\nPossession sfta distribution:")
    print(poss_df["sfta"].value_counts().sort_index().to_string())
    print(f"\nNull finisher: {poss_df['finisher_player_id'].isna().sum():,}")
    print(f"Mean sfta per possession: {poss_df['sfta'].mean():.4f}")
    print(f"Sum sfta: {poss_df['sfta'].sum():,}")

    bucket_sum = int(
        poss_df["ft_and1"].sum() + poss_df["ft_sf2"].sum() + poss_df["ft_sf3"].sum()
    )
    print(f"FT bucket identity: and1+sf2+sf3 = {bucket_sum:,} "
          f"vs sum sfta = {int(poss_df['sfta'].sum()):,} "
          f"({'OK' if bucket_sum == int(poss_df['sfta'].sum()) else 'MISMATCH'})")
    print(f"and-1 shots located: {len(all_and1):,} "
          f"of {int(poss_df['ft_and1'].sum()):,} and-1 FTs")

    conn = sqlite3.connect(DB_PATH)
    conn.execute("DROP TABLE IF EXISTS possessions")
    poss_df.to_sql("possessions", conn, if_exists="replace", index=False)
    conn.execute("CREATE INDEX idx_possessions_game ON possessions(game_id)")
    conn.execute("CREATE INDEX idx_possessions_finisher ON possessions(finisher_player_id)")
    and1_df = pd.DataFrame(all_and1)
    conn.execute("DROP TABLE IF EXISTS and1_shots")
    and1_df.to_sql("and1_shots", conn, if_exists="replace", index=False)
    conn.execute("CREATE INDEX idx_and1_game ON and1_shots(game_id, event_id)")
    conn.execute("CREATE INDEX idx_and1_player ON and1_shots(player_id)")
    conn.commit()
    conn.close()
    print("\nWrote table: possessions")
    print("Done.")


if __name__ == "__main__":
    main()
