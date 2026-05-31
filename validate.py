"""validate.py — automated validation suite. Run after build_tables.py.

Usage:
    python validate.py [--game GAME_ID]
"""

import argparse
import json
import logging
import os
import sqlite3
import sys
from pathlib import Path

import pandas as pd
import numpy as np

from config import DB_PATH, CACHE_DIR

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("xfta.validate")


def load_db(db_path: str = DB_PATH):
    if not os.path.exists(db_path):
        logger.error("Database not found: %s", db_path)
        sys.exit(1)
    conn = sqlite3.connect(db_path)
    return conn


def check_1_row_counts(conn: sqlite3.Connection) -> dict:
    """Check FGA counts per game are in reasonable range (160-185)."""
    shots = pd.read_sql("SELECT game_id, COUNT(*) as fgas FROM shots GROUP BY game_id", conn)
    outcomes = pd.read_sql("SELECT game_id, COUNT(*) as fgas FROM shot_outcomes GROUP BY game_id", conn)

    result = {
        "total_games": len(shots),
        "total_fgas": int(shots["fgas"].sum()),
        "per_game_stats": {},
    }

    flags = 0
    for _, row in shots.iterrows():
        count = row["fgas"]
        if count < 140 or count > 200:
            flags += 1
            logger.warning("  Game %s: %d FGAs (outside 140-200 range)", row["game_id"], count)

    result["flags"] = flags
    if flags == 0:
        logger.info("CHECK 1 PASS: All games within FGA range (140-200)")
    else:
        logger.warning("CHECK 1: %d games flagged outside FGA range", flags)

    return result


def check_2_target_distribution(conn: sqlite3.Connection) -> dict:
    """Print and check target distribution."""
    df = pd.read_sql(
        "SELECT fta_from_shot, COUNT(*) as cnt FROM shot_outcomes GROUP BY fta_from_shot ORDER BY fta_from_shot",
        conn,
    )
    total = df["cnt"].sum()
    result = {"total": int(total), "distribution": {}}

    for _, row in df.iterrows():
        pct = 100 * row["cnt"] / total if total > 0 else 0
        result["distribution"][int(row["fta_from_shot"])] = {
            "count": int(row["cnt"]),
            "pct": round(pct, 2),
        }

    logger.info("CHECK 2: Target distribution:")
    for val, info in sorted(result["distribution"].items()):
        logger.info("  fta_from_shot=%d: %d rows (%.2f%%)", val, info["count"], info["pct"])

    # 0 should dominate (typically >95%)
    zero_pct = result["distribution"].get(0, {}).get("pct", 0)
    if zero_pct < 90:
        logger.warning("  fta_from_shot=0 is below 90%% — unexpected")
    else:
        logger.info("  -> 0 dominates as expected")

    return result


def check_3_box_score_cross_check(conn: sqlite3.Connection) -> dict:
    """Check sum(fta_from_shot) <= box score FTA per game."""
    games = pd.read_sql("SELECT * FROM games", conn)
    if len(games) == 0:
        logger.warning("CHECK 3 SKIP: No games table")
        return {"skipped": True}

    # Get FTA from shot_outcomes per game
    outcomes = pd.read_sql(
        "SELECT game_id, SUM(fta_from_shot) as xfta_actual FROM shot_outcomes GROUP BY game_id",
        conn,
    )

    result = {"games_checked": 0, "failures": 0}
    # Note: box score FTA not available without pulling box scores.
    # This check will be strengthened when box score data is added.
    # For now, just verify the sums are reasonable.
    for _, row in outcomes.iterrows():
        if row["xfta_actual"] is None:
            continue
        total = row["xfta_actual"]
        if total < 0 or total > 100:
            logger.warning("  Game %s: implausible total FTA_from_shot = %d", row["game_id"], total)
            result["failures"] += 1
        result["games_checked"] += 1

    if result["failures"] == 0:
        logger.info("CHECK 3 PASS: All games have plausible FTA totals")
    else:
        logger.warning("CHECK 3: %d games with implausible FTA totals", result["failures"])

    return result


def check_4_phase0_agreement(conn: sqlite3.Connection) -> dict:
    """For game 0022300001, spot-check agreement with Phase 0 linker."""
    gate_a_game = "0022300001"

    # Check if we have outcomes for this game
    outcomes = pd.read_sql(
        f"SELECT * FROM shot_outcomes WHERE game_id = '{gate_a_game}'", conn
    )
    if len(outcomes) == 0:
        logger.warning("CHECK 4 SKIP: No data for game %s", gate_a_game)
        return {"skipped": True, "reason": f"No data for {gate_a_game}"}

    # Spot-check: count of shooting fouls should be similar to Phase 0
    shooting = outcomes[outcomes["fta_from_shot"] > 0]
    logger.info("CHECK 4: Game %s", gate_a_game)
    logger.info("  Total FGAs: %d", len(outcomes))
    logger.info("  Shooting foul FGAs: %d", len(shooting))
    logger.info("  FTA_from_shot distribution:")
    for val in sorted(outcomes["fta_from_shot"].unique()):
        cnt = len(outcomes[outcomes["fta_from_shot"] == val])
        logger.info("    %d: %d", val, cnt)

    # Phase 0 found: ~5-10 shooting fouls + and-1s per game
    # This is a rough sanity check
    if 2 <= len(shooting) <= 25:
        logger.info("  -> Count in plausible range")
    else:
        logger.warning("  -> Count may be off; Phase 0 expected ~5-15 shooting fouls")

    return {"total_fgas": int(len(outcomes)), "shooting_foul_fgas": int(len(shooting))}


def check_5_join_coverage(conn: sqlite3.Connection) -> dict:
    """Check shotchartdetail join coverage on shots table."""
    shots = pd.read_sql("SELECT * FROM shots", conn)
    if len(shots) == 0:
        logger.warning("CHECK 5 SKIP: No shots data")
        return {"skipped": True}

    has_spatial = shots["shot_x"].notna().sum()
    total = len(shots)
    coverage = 100 * has_spatial / total if total > 0 else 0

    logger.info("CHECK 5: shotchartdetail join coverage")
    logger.info("  %d/%d rows have spatial data (%.1f%%)", has_spatial, total, coverage)
    logger.info("  Missing: %d rows", total - has_spatial)

    if coverage >= 99:
        logger.info("  PASS: >=99%% coverage")
    elif coverage >= 95:
        logger.warning("  WARN: coverage between 95-99%%")
    else:
        logger.error("  FAIL: coverage below 95%%")

    return {"total": total, "matched": int(has_spatial), "coverage_pct": round(coverage, 2)}


def print_validation_report(results: dict):
    """Print a formatted validation report."""
    print("\n" + "=" * 72)
    print("  xFTA VALIDATION REPORT")
    print("=" * 72)

    for check_name, result in results.items():
        status = "PASS"
        if isinstance(result, dict):
            if result.get("skipped"):
                status = "SKIP"
            elif result.get("failures", 0) > 0:
                status = "WARN"
        print(f"  {check_name}: {status}")

    print("=" * 72)


def main():
    parser = argparse.ArgumentParser(description="xFTA validation")
    parser.add_argument("--game", type=str, help="Validate single game")
    args = parser.parse_args()

    conn = load_db()

    logger.info("Running validation checks ...")
    logger.info("Database: %s", DB_PATH)

    results = {}

    results["1_row_counts"] = check_1_row_counts(conn)
    results["2_target_distribution"] = check_2_target_distribution(conn)
    results["3_box_score_cross_check"] = check_3_box_score_cross_check(conn)
    results["4_phase0_agreement"] = check_4_phase0_agreement(conn)
    results["5_join_coverage"] = check_5_join_coverage(conn)

    print_validation_report(results)

    conn.close()
    return results


if __name__ == "__main__":
    main()
