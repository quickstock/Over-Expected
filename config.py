"""xFTA configuration — feature lists, seasons, and constants.

Feature *selection* happens at model time. The tables are a superset.
"""

# Seasons (regular season only), derived from the calendar so the
# pipeline rolls forward on its own each October. 2020-21 is the fixed
# earliest season (2019-20 was interrupted/bubble-distorted); the list
# always ends at the season implied by today's date, so historic
# seasons are never dropped.
import datetime as _dt

FIRST_SEASON_START = 2020


def _season_str(start_year: int) -> str:
    return f"{start_year}-{str(start_year + 1)[-2:]}"


def _current_season_start(today: "_dt.date | None" = None) -> int:
    d = today or _dt.date.today()
    # NBA seasons start in October; July-September still belongs to the
    # season that just finished.
    return d.year if d.month >= 10 else d.year - 1


SEASONS = [
    _season_str(y)
    for y in range(FIRST_SEASON_START, _current_season_start() + 1)
]

# Prior-season mapping for player-rate leakage prevention
PRIOR_SEASON = {
    _season_str(y): _season_str(y - 1)
    for y in range(FIRST_SEASON_START, _current_season_start() + 1)
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

import os
# Database — relative to the xFTA project root (the directory this file
# lives in), so it works no matter which directory the process is
# launched from.
_REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(_REPO_ROOT, "xfta.db")


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
