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
    playerindex,
)
from config import SEASONS, PRIOR_SEASON, CACHE_DIR, GATE_A_GAME_ID, CURRENT_SEASON
from nba_api.stats.library.http import NBAStatsHTTP

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


def _retry_call(fn, name, max_retries=4):
    """Call fn with exponential backoff retry on timeout/connection errors.

    An empty body (JSONDecodeError) is stats.nba.com throttling, not a bad
    request: it clears after tens of seconds, so it backs off much longer."""
    import json
    import random
    from requests.exceptions import Timeout, ConnectionError, ReadTimeout

    for attempt in range(max_retries + 1):
        try:
            _rate_limit()
            return fn()
        except (Timeout, ConnectionError, ReadTimeout, json.JSONDecodeError) as e:
            if attempt < max_retries:
                # A throttled keep-alive connection keeps hanging while a new
                # one is answered at once (2026-10-22: the pull timed out on a
                # game a fresh process fetched in 0.5 s), so drop the session.
                NBAStatsHTTP.set_session(None)
                throttled = isinstance(e, json.JSONDecodeError)
                wait = (15 * 2 ** attempt if throttled else 2 ** attempt) + random.uniform(0, 1)
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
    # the current season keeps adding games; never trust a frozen list
    if season != SEASONS[-1] and os.path.exists(path):
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
def normalize_scores(df: pd.DataFrame) -> pd.DataFrame:
    """Blank the 0-0 score stamps older feeds put on rows mid-game.

    Current feeds stamp the score on scoring rows and leave the rest blank,
    and every reader carries the last stamp forward. Many older feeds stamp
    the non-scoring rows 0-0 instead (19 of 25 sampled 1996-97 games; none of
    25 from 2025-26), which every reader took as a tied game: 45% of 1996-97
    shots came out at a margin of 0, against 5% in every live season. A 0-0
    stamp after the first basket is a missing value, so it becomes the blank
    a current feed would carry. Current feeds come back unchanged."""
    order = df["actionNumber"].sort_values(kind="mergesort").index
    sh = pd.to_numeric(df.loc[order, "scoreHome"], errors="coerce")
    sa = pd.to_numeric(df.loc[order, "scoreAway"], errors="coerce")
    started = (sh.fillna(0) + sa.fillna(0)).cummax() > 0
    bogus = ((sh == 0) & (sa == 0) & started).reindex(df.index)
    df = df.copy()
    df.loc[bogus, ["scoreHome", "scoreAway"]] = ""
    return df


def normalize_cached(season: str) -> int:
    """normalize_scores over one season's cached play-by-play, in place."""
    games = pull_game_list(season)["GAME_ID"]
    n = 0
    for gid in games:
        path = os.path.join(CACHE_DIR, "pbp", f"{gid}.parquet")
        if os.path.exists(path):
            df = pd.read_parquet(path)
            out = normalize_scores(df)
            if not out[["scoreHome", "scoreAway"]].equals(df[["scoreHome", "scoreAway"]]):
                out.to_parquet(path, index=False)
                n += 1
    logger.info("%s: normalized scores in %d cached games", season, n)
    return n


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
        df = normalize_scores(pbp.get_data_frames()[0])
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
    # a current-season shot chart grows every game; refetch it each pull
    if season != SEASONS[-1] and os.path.exists(path):
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


def pull_season_shots(season: str) -> list[int]:
    """Every shot of a season, one shotchartdetail call per franchise, written
    as the per-player cache files build_tables reads. Returns the shooters.

    Replaces league-wide discovery plus one call per player. The league-wide
    call (team 0, player 0) is capped: for 1996-97 it returned 106,496 rows
    from 673 of 1,189 games, so discovery built on it missed 25-53 players a
    season in 2021-22 to 2024-25 (~1,800 shots each left without a zone). By
    franchise, 1996-97 came back complete (188,589 shots, every game) and
    matched each cached per-player chart shot for shot. ~30 calls a season
    instead of ~500. Franchise ids are stable across relocations and renames,
    so the 30 current franchises cover every season."""
    from nba_api.stats.static import teams as static_teams

    done = os.path.join(CACHE_DIR, "shots", f"_teams_{season.replace('-', '_')}.done")
    suffix = f"_{season.replace('-', '_')}.parquet"
    # a current-season shot chart grows every game; refetch it each pull
    if season != SEASONS[-1] and os.path.exists(done):
        return [int(f.split("_")[0]) for f in os.listdir(os.path.join(CACHE_DIR, "shots"))
                if f.endswith(suffix) and not f.startswith("_")]

    logger.info("Pulling %s shots by franchise ...", season)
    frames = []
    for t in static_teams.get_teams():
        df = _retry_call(
            lambda: shotchartdetail.ShotChartDetail(
                team_id=t["id"],
                player_id=0,
                season_nullable=season,
                season_type_all_star="Regular Season",
                context_measure_simple="FGA",
                timeout=120,
            ),
            f"ShotChartDetail team {t['abbreviation']} {season}",
        ).get_data_frames()[0]
        frames.append(df)
    shots = pd.concat(frames, ignore_index=True)
    dupes = shots.duplicated(["GAME_ID", "GAME_EVENT_ID"]).sum()
    if dupes:
        raise RuntimeError(f"{season}: {dupes} shots returned by two franchises")
    for pid, df in shots.groupby("PLAYER_ID"):
        df.reset_index(drop=True).to_parquet(
            os.path.join(CACHE_DIR, "shots", f"{pid}{suffix}"), index=False)
    open(done, "w").close()
    logger.info("  %d shots, %d games, %d shooters", len(shots),
                shots["GAME_ID"].nunique(), shots["PLAYER_ID"].nunique())
    return [int(p) for p in shots["PLAYER_ID"].unique()]


# ---------------------------------------------------------------------------
# Player info
# ---------------------------------------------------------------------------
_PLAYER_INDEX = None
_POSITION_WORDS = {"G": "Guard", "F": "Forward", "C": "Center"}


def _player_index() -> pd.DataFrame:
    """Every player stats.nba.com knows, historical included, in one call.
    commonplayerinfo answers an empty object for retired players (Mookie
    Blaylock, Ken Norman: probed 2026-10-22), so the archive's bios come from
    here."""
    global _PLAYER_INDEX
    if _PLAYER_INDEX is None:
        _PLAYER_INDEX = _retry_call(
            lambda: playerindex.PlayerIndex(
                historical_nullable="1", season=CURRENT_SEASON, timeout=120),
            "PlayerIndex",
        ).get_data_frames()[0].set_index("PERSON_ID")
    return _PLAYER_INDEX


def _bio_from_index(player_id: int) -> dict | None:
    """The player-index row in the shape pull_player_info caches: the fields
    build_tables (height, position, player_name) and build_stints
    (info.FIRST_NAME / LAST_NAME) read. Positions are spelled out the way
    commonplayerinfo spells them ("G-F" -> "Guard-Forward")."""
    idx = _player_index()
    if player_id not in idx.index:
        return None
    r = idx.loc[player_id]
    position = "-".join(_POSITION_WORDS.get(p, p) for p in str(r["POSITION"] or "").split("-") if p) or None
    first, last = (r["PLAYER_FIRST_NAME"] or "").strip(), (r["PLAYER_LAST_NAME"] or "").strip()
    name = f"{first} {last}".strip()
    info = {"PERSON_ID": int(player_id), "FIRST_NAME": first, "LAST_NAME": last,
            "DISPLAY_FIRST_LAST": name, "POSITION": position, "HEIGHT": r["HEIGHT"],
            "FROM_YEAR": r["FROM_YEAR"], "TO_YEAR": r["TO_YEAR"]}
    return {"info": info, "headline_stats": [], "height": r["HEIGHT"] or None,
            "position": position, "player_name": name or None, "source": "playerindex"}


def pull_player_info(player_id: int):
    """A player's bio, cached forever: the player index first (one call per
    run, covers retired players), commonplayerinfo for anyone it lacks."""
    path = os.path.join(CACHE_DIR, "players", f"{player_id}.json")
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)

    bio = _bio_from_index(int(player_id))
    if bio is not None:
        with open(path, "w") as f:
            json.dump(bio, f, default=str)
        return bio

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

    # Every shot, by franchise; the shooters come from the same pull
    player_ids = pull_season_shots(season)

    # Prior-season rates (one call per season)
    pull_prior_season_rates(season)

    # Player bios (cached forever; only new players cost a call)
    logger.info("Pulling player info for %d players ...", len(player_ids))
    for i, pid in enumerate(player_ids):
        if i % 50 == 0:
            logger.info("  Player %d/%d", i + 1, len(player_ids))
        pull_player_info(pid)

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
    parser.add_argument("--normalize-cached", action="store_true",
                        help="rewrite --season's cached play-by-play with normalize_scores, then exit")
    args = parser.parse_args()

    if args.normalize_cached:
        normalize_cached(args.season)
        return

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
