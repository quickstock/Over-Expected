"""Per-game pages for the NBA -> site/public/games-NBA-{season}.json and
gameweek-NBA-{week}.json.

One index per season (every game: teams, final score, the score its shots were
worth, the home side's win share) and one detail chunk per Monday-keyed week
(each game's shots, free throws, player lines and officials). The math lives
in games.py, shared with Euro_OE; this file only assembles each game's frames
from the NBA database and the cached play-by-play and applies the gates.

Sources. Shots: shots joined to shots_xfg (the leak-free, season-anchored xFG
the shot-making lens uses). Free throws: the cached play-by-play, because no
table keeps per-game FT makes, each valued at its shooter's season FT% shrunk
toward the league's. Player FGA / FG points / expected FG points come from
player_game_shot_value, so a line here is exactly the player's game in the
form chart.

A game is published only when its events rebuild the official final: each
side's made field goals at their value plus its made free throws must equal
the final score (the larger of the stamped scores, which never decrease).
A game that does not is left out and counted.

Gates (exit 1, nothing written):
  * under 1% of a season's games left out;
  * expected FG points within 0.5% of actual FG points per season (2% for the
    in-progress season: the anchor is on makes, not points, so a season a few
    games old drifts in points while every completed season sits inside 0.5%).
Calibration of the win share is not a failure: when the pooled ECE is not
under 0.05, or a decile with 100+ games is more than 8 points from its mean,
the win share is withheld (meta.winShare false, w null) and the pages show the
expected score alone.

Era-aware: OE_ERA=archive reads xfta_archive.db and writes the archive's files
into site/public-archive, for the seasons its own data.json lists.
"""
import json
import re
import sqlite3
import sys
import zlib
from pathlib import Path

import numpy as np
import pandas as pd

import config
from config import DB_PATH, EXPORT_DIR, TEAM_ABBREV
from games import calibration, shrunk_ft_pct, side_totals, week_key, win_share

LEAGUE = "NBA"
CM_PER_TENTH_FOOT = 3.048      # shot_x/shot_y are tenths of a foot
FG_TOL = 0.005                 # |expected - actual| FG points / actual, completed seasons
FG_TOL_IN_PROGRESS = 0.02
MAX_EXCLUDED = 0.01
ECE_MAX = 0.05
DECILE_MAX_GAP = 0.08
DECILE_MIN_N = 100
PBP_COLS = ["period", "clock", "teamId", "personId", "playerName",
            "description", "actionType", "scoreHome", "scoreAway"]
CLOCK = re.compile(r"PT(\d+)M(\d+(?:\.\d+)?)S")


def ft_made(description: str) -> bool:
    """A free throw is made unless its play-by-play line starts with MISS, with
    one more miss form: a made throw's line always carries the shooter's running
    total ('(12 PTS)'), and 98 of 1.6 million lines (2008-09 to 2016-17, a few
    earlier) carry neither that nor MISS, a bare 'Free Throw 1 of 2'. Counting
    those as makes put 18-26 games a season one point over their official final
    and past the left-out gate; treated as misses, they reconstruct."""
    return not description.startswith("MISS") and "PTS)" in description


def game_points(pbp: pd.DataFrame) -> tuple[int, int]:
    """(home, away) final points: the largest stamped score on each side.
    Scores never decrease, so the maximum is the final even when non-scoring
    rows carry blank or 0-0 stamps."""
    def top(col: str) -> int:
        best = pd.to_numeric(pbp[col], errors="coerce").max()
        return 0 if pd.isna(best) else int(best)
    return top("scoreHome"), top("scoreAway")


def sec_left(clock: str) -> int:
    """Whole seconds left in the period from a clock like 'PT09M59.00S'."""
    m = CLOCK.fullmatch(clock)
    if m is None:
        raise ValueError(f"unparseable clock {clock!r}")
    return int(round(int(m.group(1)) * 60 + float(m.group(2))))


def shot_value(shot_type: str) -> int:
    return 3 if shot_type.startswith("3") else 2


def read_game(path: Path, home: int, away: int) -> dict:
    """One cached play-by-play: the final points, each free throw (side, period,
    seconds left, shooter, made) and a name for every player it mentions."""
    pbp = pd.read_parquet(path, columns=PBP_COLS)
    # 11 cached 2000-01 games (0020000374-389) pad actionType with trailing spaces.
    ft = pbp[pbp["actionType"].str.strip() == "Free Throw"]
    side = np.select([ft["teamId"] == home, ft["teamId"] == away], [0, 1], default=-1)
    named = pbp[(pbp["personId"] > 0) & (pbp["playerName"] != "")]
    return {
        "points": game_points(pbp),
        "ft": pd.DataFrame({
            "side": side,
            "pid": ft["personId"].to_numpy(),
            "period": ft["period"].to_numpy(),
            "sec": [sec_left(c) for c in ft["clock"]],
            "made": [ft_made(d) for d in ft["description"]],
        }),
        "names": dict(zip(named["personId"], named["playerName"])),
    }


def load_shots(conn, season: str) -> pd.DataFrame:
    """The season's shots with their xFG, in game order, with the shooter's side
    (0 home, 1 away) and shot value. Coordinates become centimetres."""
    df = pd.read_sql(
        """SELECT s.game_id, s.event_id, s.player_id, s.team_id, s.period,
                  s.seconds_remaining_in_period AS sec, s.shot_made AS made,
                  s.shot_x, s.shot_y, s.shot_type, x.xfg, x.xpts,
                  g.home_team_id, g.away_team_id
           FROM shots s
           JOIN shots_xfg x ON x.game_id = s.game_id AND x.event_id = s.event_id
           JOIN games g ON g.GAME_ID = s.game_id
           WHERE g.season = ?""", conn, params=(season,))
    side =np.select([df["team_id"] == df["home_team_id"], df["team_id"] == df["away_team_id"]],
                     [0, 1], default=-1)
    if (side < 0).any():
        raise ValueError(f"{season}: {(side < 0).sum()} shots by a team that is not in its game")
    df["side"] = side
    df["value"] = df["shot_type"].map(shot_value)
    df["x"] = np.rint(df["shot_x"] * CM_PER_TENTH_FOOT).astype(int)
    df["y"] = np.rint(df["shot_y"] * CM_PER_TENTH_FOOT).astype(int)
    df["sec"] = np.rint(df["sec"]).astype(int)
    return df.sort_values(["game_id", "period", "sec", "event_id"],
                          ascending=[True, True, False, True], kind="stable")


def export_season(conn, season: str, pbp_files: dict) -> dict:
    """Everything a season publishes except the win-share-dependent fields:
    index rows (win share unrounded), chunk entries by week, and the sums the
    gates read."""
    games = pd.read_sql(
        "SELECT GAME_ID AS game_id, GAME_DATE, home_team_id, away_team_id "
        "FROM games WHERE season = ? ORDER BY GAME_DATE, GAME_ID", conn, params=(season,))
    games["date"] = pd.to_datetime(games["GAME_DATE"]).dt.date
    shots = load_shots(conn, season)
    shots_by_game = {g: d for g, d in shots.groupby("game_id", sort=False)}

    ft_season = pd.read_sql(
        "SELECT player_id, ftm, fta FROM player_season_ft WHERE season = ?", conn, params=(season,))
    league_ft = ft_season["ftm"].sum() / ft_season["fta"].sum()
    ft_pct = {int(r.player_id): shrunk_ft_pct(int(r.ftm), int(r.fta), league_ft)
              for r in ft_season.itertuples()}
    unseen_pct = shrunk_ft_pct(0, 0, league_ft)

    names = dict(pd.read_sql(
        "SELECT player_id, player_name FROM player_season WHERE season = ?", conn,
        params=(season,)).itertuples(index=False, name=None))
    lines = pd.read_sql(
        "SELECT player_id, game_id, fga, act_fg_pts, exp_fg_pts "
        "FROM player_game_shot_value WHERE season = ?", conn, params=(season,))
    lines_by_game = {g: d for g, d in lines.groupby("game_id", sort=False)}
    meta = pd.read_sql(
        """SELECT m.* FROM game_meta m JOIN games g ON g.GAME_ID = m.game_id
           WHERE g.season = ?""", conn, params=(season,)).set_index("game_id")

    rows, chunks = [], {}
    wins, home_won = [], []
    xpts_sum = act_sum = 0.0
    out = {"no_pbp": 0, "no_shots": 0, "no_team": 0, "mismatch": 0}
    name_fallbacks = 0

    for g in games.itertuples(index=False):
        gid, home, away = g.game_id, int(g.home_team_id), int(g.away_team_id)
        if gid not in pbp_files:
            out["no_pbp"] += 1
            continue
        if gid not in shots_by_game:
            out["no_shots"] += 1
            continue
        pbp = read_game(pbp_files[gid], home, away)
        fts = pbp["ft"]
        if (fts["side"] < 0).any():
            out["no_team"] += 1
            continue
        fts["pct"] = fts["pid"].map(ft_pct).fillna(unseen_pct)
        sh = shots_by_game[gid]
        tot = side_totals(sh, fts)
        hs, as_ = pbp["points"]
        if (tot[0]["fg"] + tot[0]["ftm"], tot[1]["fg"] + tot[1]["ftm"]) != (hs, as_):
            out["mismatch"] += 1
            continue

        xpts_sum += float(sh["xpts"].sum())
        act_sum += tot[0]["fg"] + tot[1]["fg"]
        share = win_share(sh, fts, seed=zlib.crc32(f"{LEAGUE}{gid}".encode()))
        wins.append(share)
        home_won.append(1.0 if hs > as_ else 0.0 if hs < as_ else 0.5)

        # Player lines: FG from the same table the form chart reads, FT from the pbp.
        side_of = dict(zip(sh["player_id"], sh["side"]))
        side_of.update(zip(fts["pid"], fts["side"]))
        line = {int(r.player_id): [int(r.fga), int(round(r.act_fg_pts)), round(float(r.exp_fg_pts), 2), 0, 0]
                for r in lines_by_game[gid].itertuples()}
        for pid, made in zip(fts["pid"], fts["made"]):
            row = line.setdefault(int(pid), [0, 0, 0.0, 0, 0])
            row[3] += 1
            row[4] += int(made)
        players = []
        for pid, (fga, pts, xpts, fta, ftm) in line.items():
            if pid in names:
                name = names[pid]
            else:
                name = pbp["names"][pid]
                name_fallbacks += 1
            players.append([str(pid), name, int(side_of[pid]), fga, pts, xpts, fta, ftm])
        players.sort(key=lambda p: (p[2], -(p[4] + p[7]), p[0]))

        refs = []
        if gid in meta.index:
            m = meta.loc[gid]
            for k in (1, 2, 3):
                if pd.notna(m[f"ref{k}_id"]):
                    refs.append([str(int(m[f"ref{k}_id"])), m[f"ref{k}_name"]])

        wk = week_key(g.date)
        chunks.setdefault(wk, {})[gid] = {
            "p": players,
            "s": list(map(list, zip(
                sh["side"].tolist(), sh["player_id"].astype(str).tolist(), sh["period"].tolist(),
                sh["sec"].tolist(), sh["x"].tolist(), sh["y"].tolist(), sh["made"].tolist(),
                sh["value"].tolist(), sh["xfg"].round(3).tolist()))),
            "f": list(map(list, zip(
                fts["side"].tolist(), fts["pid"].astype(str).tolist(), fts["period"].tolist(),
                fts["sec"].tolist(), fts["made"].astype(int).tolist(),
                fts["pct"].round(3).tolist()))),
            "r": refs,
        }
        rows.append({
            "id": gid, "d": g.date.isoformat(), "wk": wk,
            "h": str(home), "a": str(away), "hl": TEAM_ABBREV[home], "al": TEAM_ABBREV[away],
            "s": [hs, as_],
            "x": [round(tot[0]["xfg"] + tot[0]["xft"], 1), round(tot[1]["xfg"] + tot[1]["xft"], 1)],
            "share": share,
        })

    excluded = sum(out.values())
    return {
        "season": season, "rows": rows, "chunks": chunks, "wins": wins, "home_won": home_won,
        "excluded": excluded, "why": out, "total": len(games), "name_fallbacks": name_fallbacks,
        "anchor": (xpts_sum - act_sum) / act_sum,
    }


def dump(obj) -> str:
    return json.dumps(obj, separators=(",", ":"), allow_nan=False, ensure_ascii=False)


def main() -> int:
    out = Path(EXPORT_DIR)
    seasons = json.loads((out / "data.json").read_text())["meta"]["seasons"]
    conn = sqlite3.connect(DB_PATH)
    pbp_files = {p.stem: p for p in config.era_pbp_files()}

    results, failures = [], []
    for s in seasons:
        r = export_season(conn, s, pbp_files)
        results.append(r)
        frac = r["excluded"] / r["total"]
        tol = FG_TOL_IN_PROGRESS if (config.ERA == "live" and s == config.CURRENT_SEASON) else FG_TOL
        why = ", ".join(f"{k} {v}" for k, v in r["why"].items() if v)
        print(f"{s}: {len(r['rows'])} games, {r['excluded']} excluded ({frac:.2%})"
              f"{' [' + why + ']' if why else ''}, FG anchor {r['anchor']:+.2%}"
              f"{', names from pbp ' + str(r['name_fallbacks']) if r['name_fallbacks'] else ''}",
              flush=True)
        if frac > MAX_EXCLUDED:
            failures.append(f"{s}: {frac:.2%} of games left out (limit {MAX_EXCLUDED:.0%})")
        if abs(r["anchor"]) > tol:
            failures.append(f"{s}: FG anchor {r['anchor']:+.2%} outside +-{tol:.1%}")

    win = np.array([w for r in results for w in r["wins"]])
    won = np.array([w for r in results for w in r["home_won"]])
    bins, ece = calibration(win, won)
    ok = ece < ECE_MAX and all(abs(b["mean"] - b["actual"]) <= DECILE_MAX_GAP
                               for b in bins if b["n"] >= DECILE_MIN_N)
    print(f"calibration: ECE {ece:.4f}, winShare {str(ok).lower()}; deciles (mean -> actual, n): "
          + ", ".join(f"{b['mean']:.3f}->{b['actual']:.3f} ({b['n']})" for b in bins))
    if not ok:
        print("WARNING: win share failed calibration; games ship without it (meta.winShare false)")

    if failures:
        print("GATE FAILED, nothing written:\n  " + "\n  ".join(failures))
        return 1

    files = {}
    for r in results:
        files[f"games-{LEAGUE}-{r['season']}.json"] = dump({
            "meta": {"league": LEAGUE, "season": r["season"], "winShare": ok,
                     "ece": round(ece, 4), "excluded": r["excluded"], "games": len(r["rows"])},
            "games": [{**{k: v for k, v in g.items() if k != "share"},
                       "w": int(round(100 * g["share"])) if ok else None} for g in r["rows"]],
        })
        for wk, chunk in r["chunks"].items():
            name = f"gameweek-{LEAGUE}-{wk}.json"
            if name in files:
                raise ValueError(f"{name} written by two seasons")
            files[name] = dump({"games": chunk})
    for name, text in files.items():
        (out / name).write_text(text, encoding="utf-8")
    print(f"wrote {len(files)} files -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
