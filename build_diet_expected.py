"""Expected free throws from shot diet: the FTAOE baseline since 2026-10-22.

Question it answers: how many shooting-foul free throws should a player have
drawn, given where he took his shots? FTAOE = actual minus this.

The previous baseline (train_possession_v4_context.py) used game context only:
clock, margin, home, opponent and crew rates. It explained ~1% of the spread
between players, so FTAOE ended up r 0.995 with the raw free-throw rate (paper
review F1) and r 0.39 with height (F16). Shot location is what separates a
rim-runner's free throws from a driver's. Measured on this data before it
shipped: r 0.70 with the raw rate, year-to-year 0.78, height r 0.05, and
r 0.85 with the independent tracking-based style baseline.

Per league-season, zones rim / paint / mid / three:
  attempts  = FGA in the zone, plus fouled misses, which are not FGAs:
              3-shot trips go to three; 2-shot trips are spread over the
              player's own 2-pt zones in proportion to his FGA there times
              the league's and-1-per-FGA propensity for that zone
  rate      = league FTs per attempt in the zone, leaving the player out
  expected  = sum over zones of attempts x rate, anchored per season so
              league expected equals league actual
Per game the same season weights and rates are applied to that game's
attempts, so a player's games sum exactly to his season.

Writes diet_game(game_id, player_id, season, xft) and
diet_rates(season, zone, attempts, fts, rate, propensity, anchor).
"""
import sqlite3

import numpy as np
import pandas as pd

from config import DB_PATH

ZONE = {"Restricted Area": "rim", "In The Paint (Non-RA)": "paint",
        "Mid-Range": "mid", "Above the Break 3": "three",
        "Left Corner 3": "three", "Right Corner 3": "three"}
TWO = ["rim", "paint", "mid"]
ZONES = TWO + ["three"]


def load(conn):
    shots = pd.read_sql(
        """SELECT s.game_id, s.event_id, s.player_id, g.season,
                  s.shot_zone_basic AS zone
           FROM shots s JOIN games g ON g.GAME_ID = s.game_id""", conn)
    shots["z"] = shots.zone.map(ZONE)
    shots = shots[shots.z.notna()].copy()
    a1 = pd.read_sql("SELECT game_id, event_id FROM and1_shots", conn)
    shots["and1"] = shots.set_index(["game_id", "event_id"]).index.isin(
        a1.set_index(["game_id", "event_id"]).index).astype(int)
    poss = pd.read_sql(
        """SELECT p.game_id, p.finisher_player_id AS player_id, g.season,
                  p.ft_sf2, p.ft_sf3
           FROM possessions p JOIN games g ON g.GAME_ID = p.game_id
           WHERE p.finisher_player_id IS NOT NULL""", conn)
    poss["player_id"] = poss.player_id.astype(int)
    shots["player_id"] = shots.player_id.astype(int)
    return shots, poss


def per_game(shots, poss):
    """(game, player, season) rows: FGA and and-1s by zone, 2- and 3-shot trips."""
    key = ["game_id", "player_id", "season"]
    fga = shots.pivot_table(index=key, columns="z", values="and1",
                            aggfunc="size", fill_value=0)
    an1 = shots.pivot_table(index=key, columns="z", values="and1",
                            aggfunc="sum", fill_value=0)
    trips = poss.groupby(key).agg(trips2=("ft_sf2", "sum"),
                                  trips3=("ft_sf3", "sum"))
    trips["trips2"] /= 2
    trips["trips3"] /= 3
    g = (fga.reindex(columns=ZONES, fill_value=0).add_prefix("fga_")
         .join(an1.reindex(columns=ZONES, fill_value=0).add_prefix("a1_"),
               how="outer")
         .join(trips, how="outer").fillna(0.0))
    return g.reset_index()


def season_model(g):
    """Per player-season allocation weights and leave-player-out zone rates
    for one season's per-game rows. Returns (player table, league rates)."""
    p = g.groupby("player_id").sum(numeric_only=True)
    prop = {z: p["a1_" + z].sum() / max(p["fga_" + z].sum(), 1) for z in TWO}
    w = np.stack([p["fga_" + z].to_numpy() * prop[z] for z in TWO], axis=1)
    tot = w.sum(axis=1, keepdims=True)
    league_w = np.array([prop[z] for z in TWO]) / sum(prop.values())
    w = np.where(tot > 0, w / np.where(tot > 0, tot, 1), league_w)
    for i, z in enumerate(TWO):
        p["w_" + z] = w[:, i]
        p["A_" + z] = p["fga_" + z] + p.trips2 * w[:, i]
        p["F_" + z] = p["a1_" + z] + 2 * p.trips2 * w[:, i]
    p["A_three"] = p.fga_three + p.trips3
    p["F_three"] = p.a1_three + 3 * p.trips3
    rates = {}
    for z in ZONES:
        A, F = p["A_" + z].sum(), p["F_" + z].sum()
        rates[z] = {"attempts": A, "fts": F, "rate": F / A,
                    "propensity": prop.get(z)}
        p["r_" + z] = (F - p["F_" + z]) / np.maximum(A - p["A_" + z], 1)
    expected = sum(p["A_" + z] * p["r_" + z] for z in ZONES)
    actual = sum(p["F_" + z] for z in ZONES)
    anchor = actual.sum() / expected.sum()
    return p, rates, anchor


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    shots, poss = load(conn)
    g = per_game(shots, poss)
    out, rate_rows = [], []
    for season, gs in g.groupby("season"):
        p, rates, anchor = season_model(gs)
        m = gs.join(p[[c for c in p.columns if c[:2] in ("w_", "r_")]],
                    on="player_id")
        xft = m.fga_three.add(m.trips3) * m.r_three
        for z in TWO:
            xft += (m["fga_" + z] + m.trips2 * m["w_" + z]) * m["r_" + z]
        out.append(pd.DataFrame({"game_id": m.game_id,
                                 "player_id": m.player_id,
                                 "season": season,
                                 "xft": xft * anchor}))
        for z, r in rates.items():
            rate_rows.append({"season": season, "zone": z, **r,
                              "anchor": anchor})
        print(f"  [{season}] anchor x{anchor:.4f}  " + "  ".join(
            f"{z} {r['rate']:.3f}" for z, r in rates.items()), flush=True)
    diet = pd.concat(out, ignore_index=True)
    conn.execute("DROP TABLE IF EXISTS diet_game")
    diet.to_sql("diet_game", conn, index=False)
    conn.execute("CREATE INDEX idx_diet_game ON diet_game(player_id, season)")
    conn.execute("DROP TABLE IF EXISTS diet_rates")
    pd.DataFrame(rate_rows).to_sql("diet_rates", conn, index=False)
    conn.commit()
    conn.close()
    print(f"diet_game: {len(diet):,} player-games, "
          f"{diet.groupby(['player_id', 'season']).ngroups:,} player-seasons")


if __name__ == "__main__":
    main()
