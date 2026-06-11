"""xFTA configuration — feature lists, seasons, and constants.

Feature *selection* happens at model time. The tables are a superset.
"""

# Seasons to pull (regular season only).
# 2020-21 is the earliest included: 2019-20 was interrupted/bubble-distorted.
SEASONS = ["2020-21", "2021-22", "2022-23", "2023-24", "2024-25", "2025-26"]

# Prior-season mapping for player-rate leakage prevention
PRIOR_SEASON = {
    "2020-21": "2019-20",
    "2021-22": "2020-21",
    "2022-23": "2021-22",
    "2023-24": "2022-23",
    "2024-25": "2023-24",
    "2025-26": "2024-25",
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

# Gate A test game
GATE_A_GAME_ID = "0022300001"
