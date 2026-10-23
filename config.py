"""xFTA configuration — feature lists, seasons, and constants.

Feature *selection* happens at model time. The tables are a superset.
"""

# Seasons (regular season only), derived from the calendar so the
# pipeline rolls forward on its own each October.
#
# Two eras, two databases. The live window (2020-21 to the current season)
# is what the Monday job rebuilds. The archive (1997-98 to 2019-20) is built
# once with OE_ERA=archive, into its own database, with the same scripts: its
# models train on its own era, and the Monday job never touches it.
#
# stats.nba.com reaches back to 1996-97, but that season's shot locations are
# coded differently: 35.7% of its shots sit at the exact rim point against ~25%
# in the seasons after, and its zone model missed by up to 6.3 points (paint)
# against a +-2 standard everywhere else. Kevin's call (2026-10-23): start at
# 1997-98 rather than ship a season that leans against rim players.
import datetime as _dt
import os

ERA = os.environ.get("OE_ERA", "live")
if ERA not in ("live", "archive"):
    raise ValueError(f"OE_ERA must be live or archive, not {ERA!r}")

FIRST_SEASON_START = 2020
ARCHIVE_FIRST_START = 1997


def _season_str(start_year: int) -> str:
    return f"{start_year}-{str(start_year + 1)[-2:]}"


def _current_season_start(today: "_dt.date | None" = None) -> int:
    d = today or _dt.date.today()
    # NBA seasons start in October; July-September still belongs to the
    # season that just finished.
    return d.year if d.month >= 10 else d.year - 1


# The calendar's season, whichever era is being built.
CURRENT_SEASON = _season_str(_current_season_start())

# OE_ARCHIVE_THROUGH=1997-98 cuts the archive short, for piloting the build on
# the first seasons pulled while the rest are still downloading.
_ARCHIVE_END = (int(os.environ["OE_ARCHIVE_THROUGH"][:4]) + 1
                if "OE_ARCHIVE_THROUGH" in os.environ else FIRST_SEASON_START)

SEASONS = (
    [_season_str(y) for y in range(ARCHIVE_FIRST_START, _ARCHIVE_END)]
    if ERA == "archive"
    else [_season_str(y) for y in range(FIRST_SEASON_START, _current_season_start() + 1)]
)

# Player tracking (drives, paint and post touches) starts here; earlier
# seasons have no style-adjusted cross-check.
TRACKING_FIRST_SEASON = "2013-14"

# Prior-season mapping for player-rate leakage prevention, both eras
PRIOR_SEASON = {
    _season_str(y): _season_str(y - 1)
    for y in range(ARCHIVE_FIRST_START, _current_season_start() + 1)
}

# Context-only model features (superset — headline model uses a subset)
CONTEXT_FEATURES = [
    "shot_distance",
    "shot_zone_basic",
    "shot_zone_area",
    "action_type",
    "shot_type",
    "period",
    "seconds_remaining_in_period",
    "score_margin",
    "in_bonus",
    "home_or_away",
    "shooter_height",
    "shooter_position",
]

# Headline model features — no player-identity signal
HEADLINE_FEATURES = [
    "shot_distance",
    "shot_zone_basic",
    "shot_zone_area",
    "action_type",
    "shot_type",
    "period",
    "seconds_remaining_in_period",
    "score_margin",
    "in_bonus",
    "home_or_away",
]

# Player-identity and prior-rate columns excluded from the headline model
HELD_OUT_FEATURES = [
    "shooter_height",
    "shooter_position",
    "prior_season_ftr",
    "prior_season_drive_rate",
]

# Carried columns — NOT used by the headline model (for future YoY variant)
CARRIED_FEATURES = [
    "prior_season_ftr",
    "prior_season_drive_rate",
]

# All feature columns in training_fga
ALL_FEATURES = CONTEXT_FEATURES + CARRIED_FEATURES

# Target column
TARGET = "fta_from_shot"

# NBA API rate limiting
NBA_API_SLEEP = 0.6          # seconds between calls
NBA_API_RETRIES = 3           # retry count
NBA_API_TIMEOUT = 60          # request timeout seconds

# Caching
CACHE_DIR = "cache"

# Database — relative to the xFTA project root (the directory this file
# lives in), so it works no matter which directory the process is
# launched from.
_REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(_REPO_ROOT, "xfta_archive.db" if ERA == "archive" else "xfta.db")
# Per-era model metrics and site export. The archive exports beside the live
# one, never over it: sync_data.py ships it as data-NBA-archive.json plus a
# players-NBA-{season}.json per archive season.
ARTIFACT_DIR = os.path.join(_REPO_ROOT, "model_artifacts", *(["archive"] if ERA == "archive" else []))
EXPORT_DIR = os.path.join(_REPO_ROOT, "site", "public-archive" if ERA == "archive" else "public")


CROSSFIT_NEIGHBOURS = 6


def crossfit_train_seasons(held: str, seasons: list) -> list:
    """The seasons a held-out season's model trains on: its nearest
    CROSSFIT_NEIGHBOURS others (earlier first on a tie). In the seven-season
    live window that is every other season, exactly as before. In the
    24-season archive it bounds memory (fitting each fold on the other 23
    seasons of possessions was killed for memory on 2026-10-23, 18 GB) and keeps
    each season's model in its own era: 1997 learns from 1994-2000, not 2019."""
    order = sorted(seasons)
    i = order.index(held)
    others = [s for s in order if s != held]
    return sorted(others, key=lambda s: (abs(order.index(s) - i), order.index(s)))[:CROSSFIT_NEIGHBOURS]


def era_pbp_files() -> list:
    """Play-by-play cache files for this era's games, in game-id order. The
    cache holds both eras, so globbing it builds an era's tables from every
    game ever pulled: the first archive pilot processed 8,422 games instead of
    1996-97's 1,189. The era's games are the DB's games table, which
    build_tables writes from this era's game lists."""
    import sqlite3
    from pathlib import Path
    con = sqlite3.connect(DB_PATH)
    ids = [r[0] for r in con.execute("SELECT GAME_ID FROM games ORDER BY GAME_ID")]
    con.close()
    pbp = Path(_REPO_ROOT) / CACHE_DIR / "pbp"
    return [p for p in (pbp / f"{g}.parquet" for g in ids) if p.exists()]


def layer_seasons() -> list:
    """Seasons the platform layers (RAPM/lineups, value, decision EV, team
    defence) fit: every season up to the base export's defaultSeason. A newer
    season has not yet cleared the qualified-player count that rolls the site
    over to it, and a handful of games cannot support the layers' per-season
    fits (RAPM's 10-fold game CV goes singular on a two-game season). Reads the
    export, which the weekly job writes before the layers run."""
    import json
    with open(os.path.join(_REPO_ROOT, "site", "public", "data.json")) as fh:
        default = json.load(fh)["meta"]["defaultSeason"]
    return [s for s in SEASONS if s <= default]

# Gate A test game
GATE_A_GAME_ID = "0022300001"


# Static stats.nba.com franchise id -> abbreviation. Public constants, not data.
TEAM_ABBREV = {
    1610612737: "ATL", 1610612738: "BOS", 1610612739: "CLE", 1610612740: "NOP",
    1610612741: "CHI", 1610612742: "DAL", 1610612743: "DEN", 1610612744: "GSW",
    1610612745: "HOU", 1610612746: "LAC", 1610612747: "LAL", 1610612748: "MIA",
    1610612749: "MIL", 1610612750: "MIN", 1610612751: "BKN", 1610612752: "NYK",
    1610612753: "ORL", 1610612754: "IND", 1610612755: "PHI", 1610612756: "PHX",
    1610612757: "POR", 1610612758: "SAC", 1610612759: "SAS", 1610612760: "OKC",
    1610612761: "TOR", 1610612762: "UTA", 1610612763: "MEM", 1610612764: "WAS",
    1610612765: "DET", 1610612766: "CHA",
}
