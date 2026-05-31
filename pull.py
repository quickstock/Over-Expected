"""pull.py — network pull only. Writes raw cache to cache/. No table-building.

Usage:
    python pull.py                    # all seasons in config
    python pull.py --game 0022300001  # single game (Gate A)
    python pull.py --season 2023-24   # single season
    python pull.py --week 1 2023-24   # first N weeks of a season
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime
from typing import Optional

import pandas as pd

from nba_api.stats.endpoints import (
    playbyplayv3,
    shotchartdetail,
    commonplayerinfo,
    leaguedashplayerstats,
    leaguedashptstats,
    leaguegamefinder,
    commonallplayers,
)
from config import SEASONS, PRIOR_SEASON, CACHE_DIR, GATE_A_GAME_ID

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("xfta.pull")

os.makedirs(CACHE_DIR, exist_ok=True)
os.makedirs(os.path.join(CACHE_DIR, "pbp"), exist_ok=True)
os.makedirs(os.path.join(CACHE_DIR, "shots"), exist_ok=True)
os.makedirs(os.path.join(CACHE_DIR, "players"), exist_ok=True)
os.makedirs(os.path.join(CACHE_DIR, "seasons"), exist_ok=True)

# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------
_last_call = 0.0
MIN_SLEEP = 0.7


def _rate_limit():
    global _last_call
    now = time.monotonic()
    elapsed = now - _last_call
    if elapsed < MIN_SLEEP:
        time.sleep(MIN_SLEEP - elapsed)
    _last_call = time.monotonic()


def _is_player_id(pid) -> bool:
    """Filter out team IDs (1610612xxx range) from player IDs."""
    try:
        pid = int(pid)
    except (ValueError, TypeError):
        return False
    if pid == 0:
        return False
    # Team IDs are 16106127xx (10 digits)
    if 1610610000 <= pid <= 1610619999:
        return False
    return True


def _retry_call(fn, name, max_retries=3):
    """Call fn with exponential backoff retry on timeout/connection errors."""
    import random
    from requests.exceptions import Timeout, ConnectionError, ReadTimeout

    for attempt in range(max_retries + 1):
        try:
            _rate_limit()
            return fn()
        except (Timeout, ConnectionError, ReadTimeout) as e:
            if attempt < max_retries:
                wait = (2 ** attempt) + random.uniform(0, 1)
                logger.warning(
                    "%s: %s (attempt %d/%d), retrying in %.1fs",
                    name, type(e).__name__, attempt + 1, max_retries, wait,
                )
                time.sleep(wait)
                _last_call = time.monotonic()
            else:
                raise

# ---------------------------------------------------------------------------
# Game list
# ---------------------------------------------------------------------------
def pull_game_list(season: str):
    """Pull all regular-season game IDs for a season."""
    path = os.path.join(CACHE_DIR, "seasons", f"games_{season}.parquet")
    if os.path.exists(path):
        logger.info("Game list %s already cached (%s)", season, path)
        return pd.read_parquet(path)

    logger.info("Pulling game list for %s ...", season)
    try:
        lgf = _retry_call(
            lambda: leaguegamefinder.LeagueGameFinder(
                season_nullable=season,
                season_type_nullable="Regular Season",
                timeout=60,
            ),
            f"LeagueGameFinder {season}",
        )
        df = lgf.get_data_frames()[0]
        games = df[["GAME_ID", "GAME_DATE"]].drop_duplicates()
        games = games.sort_values("GAME_DATE").reset_index(drop=True)
        games.to_parquet(path, index=False)
        logger.info("  %d games cached", len(games))
        return games
    except Exception as e:
        logger.error("Failed to pull game list for %s: %s", season, e)
        raise


def _get_game_weeks(game_df, num_weeks):
    """Return first num_weeks worth of game IDs."""
    game_df = game_df.copy()
    game_df["GAME_DATE"] = pd.to_datetime(game_df["GAME_DATE"])
    start = game_df["GAME_DATE"].min()
    cutoff = start + pd.Timedelta(weeks=num_weeks)
    subset = game_df[game_df["GAME_DATE"] < cutoff]
    return subset["GAME_ID"].tolist()


# ---------------------------------------------------------------------------
# Play-by-play
# ---------------------------------------------------------------------------
def pull_pbp(game_id: str):
    """Pull PlayByPlayV3 for a single game."""
    path = os.path.join(CACHE_DIR, "pbp", f"{game_id}.parquet")
    if os.path.exists(path):
        logger.debug("PBP %s already cached", game_id)
        return pd.read_parquet(path)

    logger.info("Pulling PBP for %s ...", game_id)
    try:
        pbp = _retry_call(
            lambda: playbyplayv3.PlayByPlayV3(game_id=game_id, timeout=90),
            f"PlayByPlayV3 {game_id}",
        )
        df = pbp.get_data_frames()[0]
        df.to_parquet(path, index=False)
        logger.info("  %d events cached", len(df))
        return df
    except Exception as e:
        logger.error("Failed to pull PBP for %s: %s", game_id, e)
        raise


# ---------------------------------------------------------------------------
# Shot chart detail
# ---------------------------------------------------------------------------
def pull_shotchart_player_season(player_id: int, season: str):
    """Pull shotchartdetail for one player-season. Returns DataFrame or None if empty."""
    safe_name = f"{player_id}_{season.replace('-', '_')}"
    path = os.path.join(CACHE_DIR, "shots", f"{safe_name}.parquet")
    if os.path.exists(path):
        logger.debug("Shot chart %s already cached", safe_name)
        return pd.read_parquet(path)

    logger.debug("Pulling shot chart for player %s season %s ...", player_id, season)
    try:
        scd = _retry_call(
            lambda: shotchartdetail.ShotChartDetail(
                team_id=0,
                player_id=player_id,
                season_nullable=season,
                season_type_all_star="Regular Season",
                context_measure_simple="FGA",
                timeout=60,
            ),
            f"ShotChartDetail p{player_id} s{season}",
        )
        df = scd.get_data_frames()[0]
        if df is None or len(df) == 0:
            return None
        df.to_parquet(path, index=False)
        logger.debug("  %d shots cached for p%s", len(df), player_id)
        return df
    except Exception as e:
        logger.warning("Shot chart for p%s s%s failed: %s", player_id, season, e)
        return None


def _get_player_list_for_season(season: str):
    """Get list of all player IDs active in a season."""
    path = os.path.join(CACHE_DIR, "seasons", f"players_{season}.parquet")
    if os.path.exists(path):
        return pd.read_parquet(path)

    logger.info("Discovering players for %s ...", season)
    # Pull all shots with player_id=0 to discover active players
    try:
        scd = _retry_call(
            lambda: shotchartdetail.ShotChartDetail(
                team_id=0,
                player_id=0,
                season_nullable=season,
                season_type_all_star="Regular Season",
                context_measure_simple="FGA",
                timeout=120,
            ),
            f"ShotChartDetail all {season}",
        )
        df = scd.get_data_frames()[0]
        # Also check second data frame for league averages
        players = df[["PLAYER_ID", "PLAYER_NAME", "TEAM_ID", "TEAM_NAME"]].drop_duplicates()
        players = players[players["PLAYER_ID"] != 0]
        players.to_parquet(path, index=False)
        logger.info("  %d players found", len(players))
        return players
    except Exception as e:
        logger.error("Failed to discover players for %s: %s", season, e)
        raise


# ---------------------------------------------------------------------------
# Player info
# ---------------------------------------------------------------------------
def pull_player_info(player_id: int):
    """Pull commonplayerinfo for a player."""
    path = os.path.join(CACHE_DIR, "players", f"{player_id}.json")
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)

    logger.debug("Pulling player info for %s ...", player_id)
    try:
        cpi = _retry_call(
            lambda: commonplayerinfo.CommonPlayerInfo(player_id=player_id, timeout=60),
            f"CommonPlayerInfo {player_id}",
        )
        dfs = cpi.get_data_frames()
        result = {
            "info": dfs[0].to_dict("records")[0] if len(dfs[0]) > 0 else {},
            "headline_stats": dfs[1].to_dict("records") if len(dfs) > 1 else [],
        }
        # Extract key fields
        info_row = result["info"]
        result["height"] = info_row.get("HEIGHT", None)
        result["position"] = info_row.get("POSITION", None)
        result["player_name"] = info_row.get("DISPLAY_FIRST_LAST", None)

        with open(path, "w") as f:
            json.dump(result, f, default=str)
        return result
    except Exception as e:
        logger.warning("Player info for %s failed: %s", player_id, e)
        return {"height": None, "position": None, "player_name": None}


# ---------------------------------------------------------------------------
# Prior-season rates
# ---------------------------------------------------------------------------
def pull_prior_season_rates(season: str):
    """Pull league-level player stats for prior-season FTr and drive rate."""
    prior = PRIOR_SEASON[season]
    path = os.path.join(CACHE_DIR, "seasons", f"prior_rates_{season}.parquet")
    if os.path.exists(path):
        return pd.read_parquet(path)

    logger.info("Pulling prior-season rates for %s (prior: %s) ...", season, prior)

    # FTr from LeagueDashPlayerStats
    try:
        ldps = _retry_call(
            lambda: leaguedashplayerstats.LeagueDashPlayerStats(
                season=prior, timeout=60, per_mode_detailed="PerGame"
            ),
            f"LeagueDashPlayerStats {prior}",
        )
        df = ldps.get_data_frames()[0]
        cols = ["PLAYER_ID", "PLAYER_NAME", "FTA", "FGA", "GP"]
        ft_df = df[cols].copy()
        ft_df["prior_season_ftr"] = ft_df["FTA"] / ft_df["FGA"].replace(0, None)
        ft_df = ft_df[["PLAYER_ID", "prior_season_ftr"]]
    except Exception as e:
        logger.warning("LeagueDashPlayerStats for %s failed: %s", prior, e)
        ft_df = pd.DataFrame(columns=["PLAYER_ID", "prior_season_ftr"])

    # Drive rate from LeagueDashPtStats
    try:
        ldpt = _retry_call(
            lambda: leaguedashptstats.LeagueDashPtStats(
                season=prior, timeout=60, pt_measure_type="Drives",
                per_mode_simple="PerGame", player_or_team="Player",
            ),
            f"LeagueDashPtStats Drives {prior}",
        )
        drv_df = ldpt.get_data_frames()[0]
        drv_cols = ["PLAYER_ID", "DRIVES", "GP"]
        drv_df = drv_df[drv_cols].copy()
        drv_df["prior_season_drive_rate"] = drv_df["DRIVES"] / drv_df["GP"].replace(0, None)
        drv_df = drv_df[["PLAYER_ID", "prior_season_drive_rate"]]
    except Exception as e:
        logger.warning("LeagueDashPtStats Drives for %s failed: %s", prior, e)
        drv_df = pd.DataFrame(columns=["PLAYER_ID", "prior_season_drive_rate"])

    rates = ft_df.merge(drv_df, on="PLAYER_ID", how="outer")
    rates.to_parquet(path, index=False)
    logger.info("  %d players with prior rates", len(rates))
    return rates


# ---------------------------------------------------------------------------
# Main orchestration
# ---------------------------------------------------------------------------
def pull_season(season: str, game_ids: list[str] | None = None):
    """Pull all data for a season."""
    logger.info("=" * 60)
    logger.info("Pulling season: %s", season)
    logger.info("=" * 60)

    # Game list
    all_games = pull_game_list(season)
    if game_ids is not None:
        games_to_pull = [g for g in game_ids if g in all_games["GAME_ID"].values]
    else:
        games_to_pull = all_games["GAME_ID"].tolist()

    logger.info("Games to pull: %d", len(games_to_pull))

    # Player discovery
    players = _get_player_list_for_season(season)
    player_ids = players["PLAYER_ID"].unique().tolist()

    # Prior-season rates (one call per season)
    pull_prior_season_rates(season)

    # Pull player info and shot charts (can take a while for full season)
    logger.info("Pulling player info and shot charts for %d players ...", len(player_ids))
    for i, pid in enumerate(player_ids):
        if i % 50 == 0:
            logger.info("  Player %d/%d", i + 1, len(player_ids))
        pull_player_info(pid)
        pull_shotchart_player_season(int(pid), season)

    # Pull PBP for each game
    logger.info("Pulling PBP for %d games ...", len(games_to_pull))
    failed = 0
    for i, gid in enumerate(games_to_pull):
        if i % 20 == 0:
            logger.info("  Game %d/%d", i + 1, len(games_to_pull))
        try:
            pull_pbp(str(gid))
        except Exception:
            failed += 1
            logger.warning("  Game %s failed (%d total failures)", gid, failed)
            if failed > 20:
                logger.error("Too many failures, stopping")
                break

    logger.info("Season %s pull complete. %d games, %d failures.", season, len(games_to_pull), failed)


def main():
    parser = argparse.ArgumentParser(description="xFTA data pull")
    parser.add_argument("--game", type=str, help="Pull single game ID")
    parser.add_argument("--season", type=str, help="Pull single season")
    parser.add_argument("--week", type=int, default=0, help="Number of weeks to pull (used with --season)")
    args = parser.parse_args()

    if args.game:
        game_id = args.game
        logger.info("Single-game pull: %s", game_id)
        pull_pbp(game_id)
        # Pull player info and shots for players in this game
        try:
            pbp = pd.read_parquet(os.path.join(CACHE_DIR, "pbp", f"{game_id}.parquet"))
        except Exception:
            pbp = pull_pbp(game_id)
        player_ids = [pid for pid in pbp["personId"].dropna().unique() if _is_player_id(pid)]
        season = "2023-24"  # Gate A default
        if game_id == "0022300001":
            season = "2023-24"
        for pid in player_ids:
            pull_player_info(int(pid))
            pull_shotchart_player_season(int(pid), season)
        pull_prior_season_rates(season)
        # Also pull game list for context
        pull_game_list(season)
        logger.info("Single-game pull complete.")
        return

    if args.season:
        seasons = [args.season]
    else:
        seasons = SEASONS

    for season in seasons:
        game_ids = None
        if args.week > 0:
            games = pull_game_list(season)
            game_ids = _get_game_weeks(games, args.week)
            logger.info("First %d weeks of %s: %d games", args.week, season, len(game_ids))
        pull_season(season, game_ids)


if __name__ == "__main__":
    main()
