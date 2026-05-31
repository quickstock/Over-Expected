"""xFTA configuration — feature lists, seasons, and constants.

Feature *selection* happens at model time. The tables are a superset.
"""

# Seasons to pull (regular season only)
SEASONS = ["2022-23", "2023-24", "2024-25"]

# Prior-season mapping for player-rate leakage prevention
PRIOR_SEASON = {
    "2022-23": "2021-22",
    "2023-24": "2022-23",
    "2024-25": "2023-24",
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

# Database
DB_PATH = "xfta.db"

# Gate A test game
GATE_A_GAME_ID = "0022300001"
