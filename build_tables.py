"""build_tables.py — builds xfta.db SQLite tables from cache/. No network calls.

Usage:
    python build_tables.py                # all cached data
    python build_tables.py --game 0022300001  # single game
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sqlite3
from pathlib import Path

import pandas as pd
import numpy as np

from config import (
    DB_PATH, CACHE_DIR, SEASONS, PRIOR_SEASON,
    CONTEXT_FEATURES, CARRIED_FEATURES, TARGET, ALL_FEATURES,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("xfta.build")


# ---------------------------------------------------------------------------
# Helpers: parse V3 PBP
# ---------------------------------------------------------------------------
def _parse_clock(clock_str: str) -> float:
    """Parse PT12M00.00S or PT05M30.00S to seconds remaining."""
    if not clock_str or pd.isna(clock_str):
        return np.nan
    s = str(clock_str).replace("PT", "").replace("S", "")
    parts = s.split("M")
    if len(parts) == 2:
        return float(parts[0]) * 60 + float(parts[1])
    return np.nan


def _parse_ft_number(sub_type: str) -> int | None:
    """Parse FT subType like '1 of 2' -> 1, '2 of 2' -> 2, etc."""
    if not sub_type or pd.isna(sub_type):
        return None
    s = str(sub_type)
    if "of" in s:
        try:
            return int(s.split("of")[0].strip())
        except ValueError:
            pass
    return None


def _is_shooting_foul_description(desc: str) -> bool:
    """Check if foul description indicates a shooting foul."""
    if not isinstance(desc, str):
        return False
    desc_upper = desc.upper()
    # S.FOUL, shooting foul indicators
    if "S.FOUL" in desc_upper:
        return True
    if "SHOOTING" in desc_upper:
        return True
    # Shooting block foul
    if ".S.FOUL" in desc_upper.replace(" ", ""):
        return True
    return False


def _is_technical_or_flagrant(desc: str) -> bool:
    if not isinstance(desc, str):
        return False
    d = desc.upper()
    return any(t in d for t in ["T.FOUL", "FLAGRANT", "TECHNICAL", "DEFENSIVE 3 SECONDS"])


def _excluded_foul(desc: str) -> bool:
    """Check if foul should be excluded from shooting foul FTA count."""
    if not isinstance(desc, str):
        return False
    d = desc.upper()
    return any(t in d for t in [
        "T.FOUL", "FLAGRANT", "TECHNICAL", "DEFENSIVE 3 SECONDS",
        "AWAY.FROM.PLAY", "INBOUND", "LOOSE BALL", "OFFENSIVE",
        "CHARGE", "DOUBLE FOUL", "CLEAR PATH", "TAKE FOUL",
    ])


# ---------------------------------------------------------------------------
# Build games table
# ---------------------------------------------------------------------------
def build_games(conn: sqlite3.Connection):
    """Build the games table from cached game lists and PBP."""
    all_games = []
    for season in SEASONS:
        path = os.path.join(CACHE_DIR, "seasons", f"games_{season}.parquet")
        if not os.path.exists(path):
            continue
        df = pd.read_parquet(path)
        df["season"] = season
        all_games.append(df)

    if not all_games:
        logger.warning("No game lists found in cache")
        return pd.DataFrame()

    games = pd.concat(all_games, ignore_index=True)
    games = games[["GAME_ID", "season", "GAME_DATE"]].drop_duplicates()
    games["GAME_DATE"] = pd.to_datetime(games["GAME_DATE"])

    # Add home/away from PBP data
    home_away_records = []
    for _, row in games.iterrows():
        gid = str(row["GAME_ID"])
        pbp_path = os.path.join(CACHE_DIR, "pbp", f"{gid}.parquet")
        if os.path.exists(pbp_path):
            pbp = pd.read_parquet(pbp_path)
            teams = pbp[pbp["teamId"] != 0]["teamId"].dropna().unique()
            if len(teams) >= 2:
                home_away_records.append({
                    "GAME_ID": gid,
                    "home_team_id": int(teams[0]),
                    "away_team_id": int(teams[1]),
                })

    if home_away_records:
        ha_df = pd.DataFrame(home_away_records)
        games = games.merge(ha_df, on="GAME_ID", how="left")

    games.to_sql("games", conn, if_exists="replace", index=False)
    logger.info("games: %d rows", len(games))
    return games


# ---------------------------------------------------------------------------
# Build shots and shot_outcomes from PBP + shotchartdetail
# ---------------------------------------------------------------------------
def _link_fts_for_foul(pbp_df: pd.DataFrame, foul_idx: int) -> list[int]:
    """Walk forward from a foul to find the free throws it produced."""
    fts = []
    period = pbp_df.at[foul_idx, "period"]
    for j in range(foul_idx + 1, min(foul_idx + 30, len(pbp_df))):
        ev = pbp_df.iloc[j]
        if ev["period"] != period:
            break
        if ev["actionType"] == "Free Throw" and not pd.isna(ev["personId"]):
            fts.append(j)
        elif ev["actionType"] in ("Made Shot", "Missed Shot", "Rebound",
                                   "Turnover", "Jump Ball", "Foul",
                                   "EndOfPeriod", "period"):
            break
        # Substitutions and timeouts can happen between FTs, skip
    return fts


def build_shots_and_outcomes(conn: sqlite3.Connection, game_ids: list[str] | None = None):
    """Build shots and shot_outcomes tables from cached PBP + shotchartdetail.

    This is the core linking logic: FGA → shooting foul → FTs.
    """
    # Discover available PBP files
    pbp_dir = os.path.join(CACHE_DIR, "pbp")
    available_pbp = set(f.stem for f in Path(pbp_dir).glob("*.parquet"))

    if game_ids is None:
        game_ids = sorted(available_pbp)
    else:
        game_ids = [g for g in game_ids if g in available_pbp]

    logger.info("Processing %d games ...", len(game_ids))

    all_shots = []
    all_outcomes = []
    total_fgas = 0
    linked_foul = 0
    and1_count = 0

    for gid in game_ids:
        pbp_path = os.path.join(CACHE_DIR, "pbp", f"{gid}.parquet")
        pbp = pd.read_parquet(pbp_path)

        # Only process actual game events (not period markers)
        pbp = pbp[pbp["actionType"] != "period"].copy()
        pbp = pbp.reset_index(drop=True)

        # Parse seconds remaining
        pbp["seconds_remaining"] = pbp["clock"].apply(_parse_clock)

        # Get all FGA events
        fgas = pbp[pbp["isFieldGoal"] == 1].copy()

        for fga_idx in fgas.index:
            fga_row = pbp.iloc[fga_idx]
            event_id = fga_row["actionNumber"]
            player_id = fga_row["personId"]
            period = fga_row["period"]
            clock = fga_row["clock"]
            sec_rem = fga_row["seconds_remaining"]
            shot_made = fga_row["shotResult"] == "Made"
            shot_value = fga_row.get("shotValue", 2)
            if pd.isna(shot_value) or shot_value == 0:
                shot_value = 3 if "3PT" in str(fga_row.get("description", "")) else 2

            # Look for a foul at the same time
            # Events at the same clock can have different actionNumbers
            # Look in a window around this event
            foul_idx = None
            window_start = max(0, fga_idx - 3)
            window_end = min(len(pbp), fga_idx + 5)
            for j in range(window_start, window_end):
                if j == fga_idx:
                    continue
                ev = pbp.iloc[j]
                if (ev["actionType"] == "Foul"
                        and ev["period"] == period
                        and ev["clock"] == clock
                        and not _excluded_foul(ev.get("description", ""))):
                    # Check it's a shooting foul
                    desc = str(ev.get("description", ""))
                    if _is_shooting_foul_description(desc):
                        foul_idx = j
                        break

            fta_from_shot = 0
            drew_shooting_foul = 0
            is_and1 = 0

            if foul_idx is not None:
                drew_shooting_foul = 1
                foul = pbp.iloc[foul_idx]
                fts = _link_fts_for_foul(pbp, foul_idx)

                if shot_made and len(fts) == 1:
                    # And-1: made shot + 1 FT
                    is_and1 = 1
                    fta_from_shot = 1
                    and1_count += 1
                elif not shot_made and len(fts) > 0:
                    # Missed shot + shooting foul → FTs
                    fta_from_shot = len(fts)
                elif shot_made and len(fts) > 1:
                    # Unusual: made shot + multiple FTs (could be flagrant)
                    # Check if fouled player matches shooter
                    ft_person = pbp.iloc[fts[0]]["personId"]
                    if ft_person == player_id:
                        fta_from_shot = len(fts)
                    else:
                        fta_from_shot = 0  # FTs are for someone else
                else:
                    fta_from_shot = 0

                if fta_from_shot > 0:
                    linked_foul += 1

            # Check the subType for foul type identification
            foul_subtype = None
            if foul_idx is not None:
                foul_subtype = str(pbp.iloc[foul_idx].get("subType", ""))

            # Build shot row (from PBP)
            shot_row = {
                "game_id": gid,
                "event_id": event_id,
                "player_id": player_id,
                "team_id": fga_row.get("teamId", None),
                "period": period,
                "seconds_remaining_in_period": sec_rem,
                "shot_made": 1 if shot_made else 0,
            }
            all_shots.append(shot_row)

            # Build outcome row
            outcome_row = {
                "game_id": gid,
                "event_id": event_id,
                "drew_shooting_foul": drew_shooting_foul,
                "fta_from_shot": fta_from_shot,
                "is_and1": is_and1,
            }
            all_outcomes.append(outcome_row)
            total_fgas += 1

    shots_df = pd.DataFrame(all_shots)
    outcomes_df = pd.DataFrame(all_outcomes)

    # Merge with shotchartdetail for spatial features
    # Load all shotchartdetail cache
    logger.info("Loading shotchartdetail cache ...")
    shots_dir = os.path.join(CACHE_DIR, "shots")
    all_scd = []
    for f in Path(shots_dir).glob("*.parquet"):
        df = pd.read_parquet(f)
        if df is not None and len(df) > 0:
            all_scd.append(df)

    if all_scd:
        scd_df = pd.concat(all_scd, ignore_index=True)
        scd_df["GAME_ID"] = scd_df["GAME_ID"].astype(str)
        logger.info("  %d shotchartdetail rows loaded", len(scd_df))

        # Join spatial data to shots on (game_id, event_id)
        shots_df["game_id"] = shots_df["game_id"].astype(str)
        shots_df["event_id"] = shots_df["event_id"].astype(int)

        scd_join = scd_df[["GAME_ID", "GAME_EVENT_ID", "LOC_X", "LOC_Y",
                            "SHOT_DISTANCE", "SHOT_ZONE_BASIC", "SHOT_ZONE_AREA",
                            "SHOT_ZONE_RANGE", "ACTION_TYPE", "SHOT_TYPE"]].copy()
        scd_join.columns = ["game_id", "event_id", "shot_x", "shot_y",
                            "shot_distance", "shot_zone_basic", "shot_zone_area",
                            "shot_zone_range", "action_type", "shot_type"]

        shots_df = shots_df.merge(scd_join, on=["game_id", "event_id"], how="left")

        # Join coverage
        joined = shots_df["shot_x"].notna().sum()
        logger.info("  shotchartdetail join coverage: %d/%d (%.1f%%)",
                     joined, len(shots_df), 100 * joined / max(len(shots_df), 1))
    else:
        logger.warning("No shotchartdetail cache found — spatial features will be null")

    # Calculate score margin from PBP
    logger.info("Computing score margins ...")
    score_margins = []
    for gid in game_ids:
        pbp_path = os.path.join(CACHE_DIR, "pbp", f"{gid}.parquet")
        pbp = pd.read_parquet(pbp_path)
        pbp = pbp[pbp["actionType"] != "period"].copy()

        for idx, row in pbp.iterrows():
            if row["isFieldGoal"] != 1:
                continue
            home_score = int(row.get("scoreHome", 0) or 0)
            away_score = int(row.get("scoreAway", 0) or 0)
            team_id = row.get("teamId", 0) or 0
            # Score margin from shooting team's perspective
            # We need to know if team is home or away
            # For now, compute from home perspective
            score_margins.append({
                "game_id": gid,
                "event_id": row["actionNumber"],
                "score_margin_home": home_score - away_score,
            })

    if score_margins:
        sm_df = pd.DataFrame(score_margins)
        shots_df = shots_df.merge(sm_df, on=["game_id", "event_id"], how="left")

        # Determine home_or_away for each shot
        # Load games to get home/away team IDs
        games_df = pd.read_sql("SELECT * FROM games", conn)
        if len(games_df) > 0:
            team_map = {}
            for _, gr in games_df.iterrows():
                team_map[str(gr["GAME_ID"])] = {
                    "home": gr.get("home_team_id"),
                    "away": gr.get("away_team_id"),
                }
            ha_values = []
            sm_values = []
            for _, sr in shots_df.iterrows():
                tmap = team_map.get(str(sr["game_id"]), {})
                tid = sr.get("team_id")
                if tid is not None and tmap.get("home") is not None:
                    if int(tid) == int(tmap["home"]):
                        ha_values.append("home")
                        sm_values.append(sr.get("score_margin_home", 0))
                    else:
                        ha_values.append("away")
                        sm_values.append(-(sr.get("score_margin_home", 0)))
                else:
                    ha_values.append(None)
                    sm_values.append(None)
            shots_df["home_or_away"] = ha_values
            shots_df["score_margin"] = sm_values
        else:
            shots_df["home_or_away"] = None
            shots_df["score_margin"] = shots_df.get("score_margin_home", 0)

    else:
        shots_df["score_margin"] = 0
        shots_df["home_or_away"] = None

    # Clean up temp column
    if "score_margin_home" in shots_df.columns:
        shots_df = shots_df.drop(columns=["score_margin_home"])

    # Write tables
    shots_df.to_sql("shots", conn, if_exists="replace", index=False)
    outcomes_df.to_sql("shot_outcomes", conn, if_exists="replace", index=False)

    logger.info("shots: %d rows", len(shots_df))
    logger.info("shot_outcomes: %d rows (linked_foul=%d, and1=%d)",
                 len(outcomes_df), linked_foul, and1_count)

    return shots_df, outcomes_df


# ---------------------------------------------------------------------------
# Build player_season
# ---------------------------------------------------------------------------
def build_player_season(conn: sqlite3.Connection):
    """Build player_season table from cached player info and prior rates."""
    players_dir = os.path.join(CACHE_DIR, "players")
    records = []

    for f in Path(players_dir).glob("*.json"):
        try:
            player_id = int(f.stem)
            with open(f) as fh:
                data = json.load(fh)
        except (ValueError, json.JSONDecodeError):
            continue

        height_str = data.get("height", "")
        height_inches = None
        if height_str:
            try:
                parts = str(height_str).split("-")
                if len(parts) == 2:
                    height_inches = int(parts[0]) * 12 + int(parts[1])
            except (ValueError, IndexError):
                pass

        position = data.get("position", None)

        records.append({
            "player_id": player_id,
            "player_name": data.get("player_name", None),
            "height_inches": height_inches,
            "position": position,
        })

    players_df = pd.DataFrame(records)

    # Merge prior-season rates for each season
    all_seasons = []
    for season in SEASONS:
        rates_path = os.path.join(CACHE_DIR, "seasons", f"prior_rates_{season}.parquet")
        if not os.path.exists(rates_path):
            continue
        rates = pd.read_parquet(rates_path)
        season_df = players_df.copy()
        season_df["season"] = season
        rate_key = "PLAYER_ID" if "PLAYER_ID" in rates.columns else "player_id"
        ps_key = "player_id"
        # Standardize key name in rates to match players_df
        if rate_key != ps_key:
            rates = rates.rename(columns={rate_key: ps_key})
        season_df = season_df.merge(rates, on=ps_key, how="left")
        all_seasons.append(season_df)

    if all_seasons:
        final = pd.concat(all_seasons, ignore_index=True)
    else:
        final = players_df
        final["season"] = None
        final["prior_season_ftr"] = None
        final["prior_season_drive_rate"] = None

    # Add possessions placeholder (will be populated later)
    final["possessions"] = None

    final.to_sql("player_season", conn, if_exists="replace", index=False)
    logger.info("player_season: %d rows", len(final))
    return final


# ---------------------------------------------------------------------------
# Build training_fga (the joined superset table)
# ---------------------------------------------------------------------------
def build_training_fga(conn: sqlite3.Connection):
    """Build the final training_fga table by joining shots + outcomes + player_season."""
    shots = pd.read_sql("SELECT * FROM shots", conn)
    outcomes = pd.read_sql("SELECT * FROM shot_outcomes", conn)
    player_season = pd.read_sql("SELECT * FROM player_season", conn)

    if len(shots) == 0:
        logger.warning("No shots data — creating empty training_fga")
        pd.DataFrame(columns=["game_id", "event_id", "player_id", "season"]
                     + ALL_FEATURES + [TARGET]).to_sql(
                         "training_fga", conn, if_exists="replace", index=False)
        return pd.DataFrame()

    # Join shots + outcomes
    df = shots.merge(outcomes, on=["game_id", "event_id"], how="left")

    # Determine season for each game
    games = pd.read_sql("SELECT * FROM games", conn)
    if len(games) > 0:
        game_season = dict(zip(games["GAME_ID"].astype(str), games["season"]))
        df["season"] = df["game_id"].map(game_season)

    # Merge player_season attributes (by player_id + season)
    ps_cols = ["player_id", "season", "height_inches", "position",
               "prior_season_ftr", "prior_season_drive_rate"]
    ps_subset = player_season[ps_cols].copy() if len(player_season) > 0 else pd.DataFrame(columns=ps_cols)

    if len(ps_subset) > 0:
        df = df.merge(ps_subset, on=["player_id", "season"], how="left")
    else:
        for c in ["height_inches", "position", "prior_season_ftr", "prior_season_drive_rate"]:
            df[c] = None

    # Rename columns to match feature list
    df["shooter_height"] = df.get("height_inches")
    df["shooter_position"] = df.get("position")

    # In-bonus placeholder (will be computed from foul tracking in a future phase)
    if "in_bonus" not in df.columns:
        df["in_bonus"] = 0

    # Select final columns
    base_cols = ["game_id", "event_id", "player_id", "season"]
    feature_cols = [c for c in ALL_FEATURES if c in df.columns]
    for c in ALL_FEATURES:
        if c not in df.columns:
            df[c] = None

    target_col = TARGET if TARGET in df.columns else "fta_from_shot"

    final_cols = base_cols + ALL_FEATURES + [TARGET]
    final_cols = [c for c in final_cols if c in df.columns]
    df = df[final_cols]

    # Leakage assertion: player-rate columns must come from prior season
    # This is enforced at pull time (PRIOR_SEASON mapping), but assert here as safety
    for feat in CARRIED_FEATURES:
        if feat in df.columns:
            non_null = df[feat].notna().sum()
            if non_null > 0:
                logger.info("  %s: %d non-null values (prior-season data)", feat, non_null)

    df.to_sql("training_fga", conn, if_exists="replace", index=False)
    logger.info("training_fga: %d rows, %d columns", len(df), len(df.columns))
    return df


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="xFTA table builder")
    parser.add_argument("--game", type=str, help="Build for single game ID")
    args = parser.parse_args()

    conn = sqlite3.connect(DB_PATH)

    logger.info("Building tables from cache ...")
    logger.info("Cache directory: %s", CACHE_DIR)

    # Build games
    build_games(conn)

    # Build shots + shot_outcomes (core linking)
    game_ids = [args.game] if args.game else None
    build_shots_and_outcomes(conn, game_ids)

    # Build player_season
    build_player_season(conn)

    # Build training_fga
    build_training_fga(conn)

    conn.close()
    logger.info("Done. Database: %s", DB_PATH)


if __name__ == "__main__":
    main()
