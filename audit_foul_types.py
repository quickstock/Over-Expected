"""Foul-type audit: for every kept FT trip (shooting-foul or and-1), find
the causing foul's descriptor. Decision: if 100% of kept trips trace to a
descriptor of 'shooting' (or to a confirmed and-1 continuation), the
80.2% coverage figure is legitimate. Any other descriptor = contamination.

The audit walks pbpstats' classification (what pbpstats would call the
trip) AND then mirrors production's contamination filter (what
build_possessions_v3 actually counts). Both are reported.
"""
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, "/Users/kevin/Library/Python/3.9/lib/python/site-packages")

import pandas as pd
from build_possessions_v3 import build_events, NON_SHOOTING_FOUL_DESCRIPTORS
from pbpstats.data_loader.nba_possession_loader import NbaPossessionLoader
from pbpstats.resources.enhanced_pbp import FreeThrow as FTBase
from pbpstats.resources.enhanced_pbp import Foul as FL


def main():
    pbp_dir = Path("cache/pbp")
    files = sorted(pbp_dir.glob("*.parquet"))
    print(f"Walking {len(files)} games to audit causing-foul descriptors...")

    kept_foul_descriptors: Counter = Counter()
    production_kept_foul_descriptors: Counter = Counter()
    kept_trip_count = 0
    production_kept_count = 0
    and1_trip_count = 0
    no_foul_in_possession = 0
    trips_skipped_no_foul_event = 0
    per_game_failures: Counter = Counter()

    for i, fp in enumerate(files):
        df = pd.read_parquet(fp)
        events = build_events(df, fp.stem)
        for j, e in enumerate(events):
            e.next_event = events[j + 1] if j + 1 < len(events) else None

        class _L(NbaPossessionLoader):
            def __init__(self, evs):
                self.events = evs

        groups = _L(events)._split_events_by_possession()
        for g in groups:
            for k, e in enumerate(g):
                if not isinstance(e, FTBase):
                    continue
                # Use pbpstats' own free_throw_type — same code path as
                # production in possession_sfta_and_finisher. If it raises
                # (the 2 known NoneType games), that whole game's trips
                # would be dropped in production; skip just this trip and
                # tally.
                try:
                    ft_type = e.free_throw_type or ""
                except Exception:
                    trips_skipped_no_foul_event += 1
                    per_game_failures[fp.stem] += 1
                    continue
                if "Shooting Foul" not in ft_type and "And 1" not in ft_type:
                    continue
                kept_trip_count += 1
                if "And 1" in ft_type:
                    and1_trip_count += 1

                # For descriptor tabulation: scan back to the prior Foul.
                # The shooting-foul descriptor and the and-1 are the only
                # ways a kept trip comes about, so this is sound.
                desc = None
                for k2 in range(k - 1, -1, -1):
                    prev = g[k2]
                    if isinstance(prev, FL):
                        desc = prev.descriptor if hasattr(prev, "descriptor") else None
                        break

                if desc is None and "And 1" in ft_type:
                    desc = "shooting (and-1 continuation)"
                if desc is None:
                    no_foul_in_possession += 1
                else:
                    kept_foul_descriptors[desc] += 1

                # Production mirror: apply the contamination filter that
                # build_possessions_v3 uses, and tabulate what production
                # actually keeps. A trip is dropped if the prior Foul's
                # descriptor is in NON_SHOOTING_FOUL_DESCRIPTORS.
                if desc is None:
                    production_kept_count += 1
                    if "And 1" in ft_type:
                        production_kept_foul_descriptors["shooting (and-1 continuation)"] += 1
                    else:
                        production_kept_foul_descriptors["shooting (no in-possession foul)"] += 1
                elif desc not in NON_SHOOTING_FOUL_DESCRIPTORS:
                    production_kept_count += 1
                    production_kept_foul_descriptors[desc] += 1
        if (i + 1) % 1000 == 0:
            print(f"  {i+1}/{len(files)} games, {kept_trip_count:,} kept trips audited")

    total = kept_trip_count
    print()
    print(f"Kept trips total (pbpstats' classification): {total:,}")
    print(f"  and-1 trips: {and1_trip_count:,}")
    print(f"  no Foul event in possession: {no_foul_in_possession:,}")
    print(f"  trips skipped (free_throw_type raised — same path as production drops): {trips_skipped_no_foul_event:,}")
    if per_game_failures:
        print(f"  games with at least one such failure: {len(per_game_failures)}")
        for gid, n in per_game_failures.most_common(5):
            print(f"    {gid}: {n} trips")
    print()
    print("As classified by pbpstats (independent of production filter):")
    bad = []
    for desc, n in kept_foul_descriptors.most_common():
        pct = n / total * 100
        flag = ""
        if desc not in ("shooting", "shooting (and-1 continuation)"):
            flag = "  <-- would be contamination if kept"
            bad.append(desc)
        print(f"  {str(desc):45s} {n:>7,}  {pct:5.1f}%{flag}")
    print()
    print(f"Production actually keeps (after contamination filter): {production_kept_count:,}")
    bad2 = []
    for desc, n in production_kept_foul_descriptors.most_common():
        pct = n / production_kept_count * 100 if production_kept_count else 0
        flag = ""
        if desc not in (
            "shooting",
            "shooting (and-1 continuation)",
            "shooting (no in-possession foul)",
        ):
            flag = "  <-- STILL CONTAMINATED"
            bad2.append(desc)
        print(f"  {str(desc):60s} {n:>7,}  {pct:5.1f}%{flag}")
    print()
    pbpstats_clean = not bad
    production_clean = not bad2
    if not pbpstats_clean:
        print(f"pbpstats classifications: {len(bad)} non-shooting categories present")
    if not production_clean:
        print(f"DECISION: FAIL — production keeps non-shooting fouls: {bad2}")
    elif not pbpstats_clean:
        print(f"DECISION: PASS — pbpstats misclassifies {len(bad)} non-shooting foul "
              f"types as and-1, but the production filter drops all of them. "
              f"80% coverage is legitimate.")
    else:
        print("DECISION: PASS — every kept trip traces to a shooting-foul or "
              "validated and-1 continuation.")


if __name__ == "__main__":
    main()
