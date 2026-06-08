"""Fixture data for Gate 1 design shell.

Hard-coded so the design can be reviewed before the data pipeline is wired in.
All FTAOE numbers here are placeholders. Percentiles are computed within the
fixture list so the inline bar reads sensibly.
"""

from __future__ import annotations

import pandas as pd


SEASONS = ["2022-23", "2023-24", "2024-25"]
POSITIONS = ["G", "F", "C"]


# 50 player-seasons. ftaoe_per_100_fga covers ~ -3.5 to +6.5 to exercise the
# diverging scale in both directions.
_LEADERBOARD_RAW = [
    # (player, team, season, pos, fga, actual_fta, xfta, ftaoe_per_100_fga)
    ("Joel Embiid",       "PHI", "2022-23", "C",  792, 504, 380.0,  15.7),
    ("Joel Embiid",       "PHI", "2023-24", "C",  640, 360, 310.0,   7.8),
    ("Joel Embiid",       "PHI", "2024-25", "C",  312, 184, 150.0,  10.9),
    ("Giannis Antetokounmpo","MIL","2022-23","F",  1095, 540, 470.0,  6.4),
    ("Giannis Antetokounmpo","MIL","2023-24","F", 1132, 600, 510.0,  7.9),
    ("Giannis Antetokounmpo","MIL","2024-25","F", 1108, 612, 540.0,  6.5),
    ("Trae Young",        "ATL", "2022-23", "G",  900, 312, 248.0,  7.1),
    ("Trae Young",        "ATL", "2023-24", "G",  980, 350, 295.0,  5.6),
    ("Trae Young",        "ATL", "2024-25", "G", 1010, 330, 300.0,  3.0),
    ("Luka Doncic",       "DAL", "2022-23", "G",  912, 410, 348.0,  6.8),
    ("Luka Doncic",       "DAL", "2023-24", "G", 1024, 478, 402.0,  7.4),
    ("Luka Doncic",       "DAL", "2024-25", "G", 1008, 470, 410.0,  6.0),
    ("James Harden",      "LAC", "2022-23", "G",  756, 312, 250.0,  8.2),
    ("James Harden",      "LAC", "2023-24", "G",  820, 340, 286.0,  6.6),
    ("James Harden",      "LAC", "2024-25", "G",  790, 295, 268.0,  3.4),
    ("Damian Lillard",    "MIL", "2023-24", "G",  868, 290, 254.0,  4.1),
    ("Damian Lillard",    "MIL", "2024-25", "G",  840, 268, 240.0,  3.3),
    ("Jimmy Butler",      "MIA", "2022-23", "F",  680, 280, 235.0,  6.6),
    ("Jimmy Butler",      "MIA", "2023-24", "F",  720, 305, 250.0,  7.6),
    ("De'Aaron Fox",      "SAC", "2023-24", "G", 1015, 388, 320.0,  6.7),
    ("De'Aaron Fox",      "SAC", "2024-25", "G",  985, 372, 318.0,  5.5),
    ("Shai Gilgeous-Alexander","OKC","2022-23","G", 1080, 402, 360.0,  3.9),
    ("Shai Gilgeous-Alexander","OKC","2023-24","G", 1124, 458, 410.0,  4.3),
    ("Shai Gilgeous-Alexander","OKC","2024-25","G", 1100, 480, 420.0,  5.5),
    ("Anthony Edwards",   "MIN", "2022-23", "G",  900, 285, 252.0,  3.7),
    ("Anthony Edwards",   "MIN", "2023-24", "G", 1056, 358, 318.0,  3.8),
    ("Anthony Edwards",   "MIN", "2024-25", "G", 1110, 392, 348.0,  4.0),
    ("Nikola Jokic",      "DEN", "2022-23", "C",  990, 360, 340.0,  2.0),
    ("Nikola Jokic",      "DEN", "2023-24", "C", 1100, 412, 390.0,  2.0),
    ("Nikola Jokic",      "DEN", "2024-25", "C", 1120, 430, 405.0,  2.2),
    ("Stephen Curry",     "GSW", "2022-23", "G", 1180, 252, 264.0, -1.0),
    ("Stephen Curry",     "GSW", "2023-24", "G", 1112, 238, 248.0, -0.9),
    ("Stephen Curry",     "GSW", "2024-25", "G", 1090, 230, 240.0, -0.9),
    ("Klay Thompson",     "GSW", "2022-23", "G",  970, 192, 212.0, -2.1),
    ("Klay Thompson",     "GSW", "2023-24", "G",  990, 188, 218.0, -3.0),
    ("Klay Thompson",     "DAL", "2024-25", "G",  890, 158, 196.0, -4.3),
    ("Donovan Mitchell",  "CLE", "2022-23", "G", 1180, 408, 380.0,  2.4),
    ("Donovan Mitchell",  "CLE", "2023-24", "G", 1140, 410, 384.0,  2.3),
    ("Donovan Mitchell",  "CLE", "2024-25", "G", 1100, 395, 372.0,  2.1),
    ("Devin Booker",      "PHX", "2022-23", "G", 1180, 348, 340.0,  0.7),
    ("Devin Booker",      "PHX", "2023-24", "G", 1220, 372, 358.0,  1.1),
    ("Devin Booker",      "PHX", "2024-25", "G", 1140, 350, 348.0,  0.2),
    ("Jayson Tatum",      "BOS", "2022-23", "F", 1180, 348, 332.0,  1.4),
    ("Jayson Tatum",      "BOS", "2023-24", "F", 1280, 390, 365.0,  2.0),
    ("Jayson Tatum",      "BOS", "2024-25", "F", 1240, 405, 378.0,  2.2),
    ("Jalen Brunson",     "NYK", "2022-23", "G",  920, 320, 280.0,  4.3),
    ("Jalen Brunson",     "NYK", "2023-24", "G", 1180, 442, 388.0,  4.6),
    ("Jalen Brunson",     "NYK", "2024-25", "G", 1200, 460, 405.0,  4.6),
    ("Tyrese Haliburton", "IND", "2022-23", "G",  890, 246, 240.0,  0.7),
    ("Tyrese Haliburton", "IND", "2023-24", "G", 1180, 312, 310.0,  0.2),
    ("Tyrese Haliburton", "IND", "2024-25", "G", 1100, 308, 295.0,  1.2),
    ("Kevin Durant",      "PHX", "2022-23", "F",  980, 318, 308.0,  1.0),
    ("Kevin Durant",      "PHX", "2023-24", "F", 1080, 350, 336.0,  1.3),
    ("Kevin Durant",      "PHX", "2024-25", "F", 1060, 348, 332.0,  1.5),
    ("Anthony Davis",     "LAL", "2022-23", "F/C", 940, 460, 408.0,  5.5),
    ("Anthony Davis",     "LAL", "2023-24", "F/C",1020, 510, 450.0,  5.9),
    ("Anthony Davis",     "LAL", "2024-25", "F/C",1000, 522, 462.0,  6.0),
    ("Zion Williamson",   "NOP", "2022-23", "F",  780, 320, 268.0,  6.7),
    ("Zion Williamson",   "NOP", "2023-24", "F",  820, 348, 290.0,  7.1),
    ("Zion Williamson",   "NOP", "2024-25", "F",  840, 360, 305.0,  6.5),
    ("Ja Morant",         "MEM", "2022-23", "G", 1050, 388, 320.0,  6.5),
    ("Ja Morant",         "MEM", "2023-24", "G",  680, 240, 198.0,  6.2),
    ("Ja Morant",         "MEM", "2024-25", "G",  910, 318, 268.0,  5.5),
    ("Paul George",       "LAC", "2022-23", "F",  920, 240, 250.0, -1.1),
    ("Paul George",       "PHI", "2024-25", "F",  860, 228, 232.0, -0.5),
    ("Kawhi Leonard",     "LAC", "2022-23", "F",  780, 230, 238.0, -1.0),
    ("Kawhi Leonard",     "LAC", "2023-24", "F",  860, 268, 268.0,  0.0),
    ("Kawhi Leonard",     "LAC", "2024-25", "F",  920, 295, 290.0,  0.5),
    ("Jaylen Brown",      "BOS", "2022-23", "F", 1080, 320, 310.0,  0.9),
    ("Jaylen Brown",      "BOS", "2023-24", "F", 1180, 360, 342.0,  1.5),
    ("Jaylen Brown",      "BOS", "2024-25", "F", 1140, 372, 350.0,  1.9),
    ("Pascal Siakam",     "IND", "2023-24", "F", 1140, 348, 320.0,  2.5),
    ("Pascal Siakam",     "IND", "2024-25", "F", 1100, 332, 308.0,  2.2),
    ("Bam Adebayo",       "MIA", "2022-23", "C",  980, 360, 330.0,  3.1),
    ("Bam Adebayo",       "MIA", "2023-24", "C", 1020, 392, 358.0,  3.3),
    ("Bam Adebayo",       "MIA", "2024-25", "C", 1080, 420, 388.0,  3.0),
    ("Domantas Sabonis",  "SAC", "2022-23", "C",  980, 410, 370.0,  4.1),
    ("Domantas Sabonis",  "SAC", "2023-24", "F/C",1080, 432, 402.0,  2.8),
    ("Karl-Anthony Towns","MIN", "2022-23", "C", 1080, 388, 360.0,  2.6),
    ("Karl-Anthony Towns","NYK", "2024-25", "C", 1040, 372, 348.0,  2.3),
    ("Brunson Booker Doncic", "—", "—", "—", 0,0,0,0),  # sentinel — will be removed
]

# Trim sentinel & coerce to DataFrame
_LEADERBOARD_RAW = [r for r in _LEADERBOARD_RAW if r[0] != "Brunson Booker Doncic"]


def get_fixture_leaderboard() -> pd.DataFrame:
    """Return a styled DataFrame with the fixture leaderboard data.

    Columns: player_name, team, season, position, fga, actual_fta_from_fouls,
             xfta_total, ftaoe, ftaoe_per_100_fga, percentile.
    """
    df = pd.DataFrame(
        _LEADERBOARD_RAW,
        columns=[
            "player_name", "team", "season", "position",
            "fga", "actual_fta_from_fouls", "xfta_total", "ftaoe_per_100_fga",
        ],
    )
    df["ftaoe"] = df["actual_fta_from_fouls"] - df["xfta_total"]
    # Percentile within fixture set
    df["percentile"] = df["ftaoe_per_100_fga"].rank(pct=True) * 100
    return df


def get_fixture_player(player_name: str) -> dict | None:
    """Return the row with the largest FGA for a given player (the marquee season)."""
    df = get_fixture_leaderboard()
    rows = df[df["player_name"] == player_name]
    if len(rows) == 0:
        return None
    return rows.sort_values("fga", ascending=False).iloc[0].to_dict()
