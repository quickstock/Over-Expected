"""Per-game pages for the NBA -> site/public/games-NBA-{season}.json and
gameweek-NBA-{week}.json.

One index per season (every game: teams, final score, the score its shots were
worth, the home side's win share) and one detail chunk per Monday-keyed week
(each game's shots, free throws, player lines and officials). The math lives
in games.py, shared with Euro_OE; this file only assembles each game's frames
from the NBA database and the cached play-by-play and applies the gates.

Sources. Shots: shots joined to shots_xfg (the leak-free, season-anchored xFG
the shot-making lens uses). A few hundred shots, clustered in 2015-16 and
2016-17, have no location in the shot-chart feed and so no xFG: they still
count, with no coordinates and the xFG the season's league makes shots of that
value at, because leaving them out left up to 4.6% of a season's games unable
to rebuild their final. Free throws: the cached play-by-play, because no table
keeps per-game FT makes, each valued at its shooter's season FT% shrunk toward
the league's. Player FGA / FG points / expected FG points start from
player_game_shot_value (the form chart's numbers) plus any unlocated shots.
Team labels are the play-by-play's own tricode for that game (SEA, VAN, NJN
before they moved), falling back to config.TEAM_ABBREV.

A game is published only when its events rebuild the official final: each
side's made field goals at their value plus its made free throws must equal
the final score (the larger of the stamped scores, which never decrease).
A game that does not is left out and counted.

Gates (exit 1, nothing written):
  * no more than max(1% of a season's games, 3) left out;
  * expected FG points within 0.5% of actual FG points per season (2% for the
    in-progress season: the anchor is on makes, not points, so a season a few
    games old drifts in points while every completed season sits inside 0.5%).
Calibration of the win share is not a failure: when the pooled ECE is not
under 0.05, or a decile with 100+ games is more than 8 points from its mean,
the win share is withheld (meta.winShare false, w null) and the pages show the
expected score alone.

A chunk's per-game detail is columnar (a shot's side is its player's side):
  p  [[pid, name, side, fga, fgPts, xFgPts, fta, ftm]]  every player in the game
  s  {p: index into p, q: period, c: seconds left, x, y: cm or null,
      m: "0110", v: "2323", e: xFG in thousandths}
  f  {p, q, c, m: "0110", e: shrunk FT% in thousandths}
  r  [[refId, name]]

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
LEFT_OUT_PERCENT = 1           # a season may leave out this share of its games ...
LEFT_OUT_MIN = 3               # ... but never fewer than this many (ruling 7)
XFG_TIE = 0.05                 # a side's player xFgPts may differ from its expected FG points by this much
ECE_MAX = 0.05
DECILE_MAX_GAP = 0.08
DECILE_MIN_N = 100
PBP_COLS = ["actionNumber", "period", "clock", "teamId", "teamTricode", "personId", "playerName",
            "description", "actionType", "isFieldGoal", "shotValue", "scoreHome", "scoreAway"]
SHOT_COLS = ["player_id", "event_id", "period", "sec", "x", "y", "made", "value", "xfg", "xpts", "side"]
CLOCK = re.compile(r"PT(\d+)M(\d+(?:\.\d+)?)S")


def ft_made(description: str) -> bool:
    """Made unless the line starts with MISS or lacks the '(N PTS)' tag: 98 archive lines are a bare 'Free Throw 1 of 2' and are misses (the reconstruction gate proves it)."""
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


def team_labels(pbp: pd.DataFrame) -> dict[int, str]:
    """Team id -> its most common non-blank tricode in this game's play-by-play,
    the franchise's code as of the game (SEA in 1997-98, OKC from 2008-09)."""
    t = pbp[["teamId", "teamTricode"]].dropna()
    t = t.assign(teamTricode=t["teamTricode"].str.strip())
    t = t[(t["teamId"] > 0) & (t["teamTricode"] != "")]
    return {int(k): v.value_counts().idxmax() for k, v in t.groupby("teamId")["teamTricode"]}


def make_rates(located: pd.DataFrame) -> dict[int, float]:
    """The league's make rate by shot value (2 or 3) over a season's located shots."""
    return {int(v): float(r) for v, r in located.groupby("value")["made"].mean().items()}


def place_unlocated(un: pd.DataFrame, rates: dict[int, float]) -> pd.DataFrame:
    """Give shots that have no location the xFG the league makes shots of their
    value at (value column filled), and no coordinates."""
    un = un.copy()
    un["xfg"] = un["value"].map(rates)
    un["xpts"] = un["xfg"] * un["value"]
    un["x"] = np.nan
    un["y"] = np.nan
    return un


def cm(values) -> list:
    """Centimetres as ints, null where a shot has no location."""
    return [None if v != v else int(v) for v in values]


def shot_block(sh: pd.DataFrame, idx: dict) -> dict:
    """A game's shots as columns, chronological. idx maps player id -> row of the game's p list."""
    return {
        "p": [idx[p] for p in sh["player_id"]],
        "q": sh["period"].astype(int).tolist(),
        "c": sh["sec"].astype(int).tolist(),
        "x": cm(sh["x"]),
        "y": cm(sh["y"]),
        "m": "".join(str(int(m)) for m in sh["made"]),
        "v": "".join(str(int(v)) for v in sh["value"]),
        "e": np.rint(sh["xfg"].to_numpy(dtype=float) * 1000).astype(int).tolist(),
    }


def ft_block(fts: pd.DataFrame, idx: dict) -> dict:
    """A game's free throws as columns, in play order; e is the shooter's shrunk FT% in thousandths."""
    return {
        "p": [idx[p] for p in fts["pid"]],
        "q": fts["period"].astype(int).tolist(),
        "c": fts["sec"].astype(int).tolist(),
        "m": "".join("1" if m else "0" for m in fts["made"]),
        "e": np.rint(fts["pct"].to_numpy(dtype=float) * 1000).astype(int).tolist(),
    }


def anchor_tolerance(season: str) -> float:
    """How far a season's expected FG points may sit from its actual FG points: 0.5%,
    or 2% for the live era's in-progress season (the anchor is on makes, not points)."""
    return FG_TOL_IN_PROGRESS if (config.ERA == "live" and season == config.CURRENT_SEASON) else FG_TOL


def left_out_limit(n_games: int) -> int:
    """The most games a season may leave out: 1% of its games, never fewer than three."""
    return max(n_games * LEFT_OUT_PERCENT // 100, LEFT_OUT_MIN)


def shooter_sides(sh: pd.DataFrame, fts: pd.DataFrame) -> "dict | None":
    """Player id -> side for everyone who shot or took a free throw, or None when a
    player's free throws are on a different team than his shots."""
    side_of = dict(zip(sh["player_id"], sh["side"]))
    for pid, side in zip(fts["pid"], fts["side"]):
        if side_of.get(pid, side) != side:
            return None
        side_of[pid] = side
    return side_of


def officials(meta: pd.DataFrame, gid: str) -> list:
    """[[id, name]] for each official game_meta lists (ids as strings); none before
    2003-04, and none for a game with no game_meta row."""
    if gid not in meta.index:
        return []
    m = meta.loc[gid]
    return [[str(int(m[f"ref{k}_id"])), m[f"ref{k}_name"]] for k in (1, 2, 3) if pd.notna(m[f"ref{k}_id"])]


def player_lines(gid: str, sh: pd.DataFrame, un: "pd.DataFrame | None", fts: pd.DataFrame,
                 pgsv: "pd.DataFrame | None", side_of: dict, names: dict, pbp_names: dict,
                 expected_fg: dict) -> tuple[list, int]:
    """A game's [pid, name, side, fga, fgPts, xFgPts, fta, ftm] rows, and how many names
    came from the pbp. FG numbers start from player_game_shot_value (pgsv; the form chart's),
    plus the unlocated shots (un) at their xpts; free throws from the pbp. Everyone in the
    game's shots or free throws gets a row. Raises when a side's xFgPts do not add up to
    expected_fg[side], the expected FG points its shots are worth."""
    line = {}
    if pgsv is not None:
        for r in pgsv.itertuples():
            line[int(r.player_id)] = [int(r.fga), int(round(r.act_fg_pts)), float(r.exp_fg_pts), 0, 0]
    for pid in sh["player_id"]:
        line.setdefault(int(pid), [0, 0, 0.0, 0, 0])
    if un is not None:
        for pid, made, value, xpts in zip(un["player_id"], un["made"], un["value"], un["xpts"]):
            row = line[int(pid)]
            row[0] += 1
            row[1] += int(made) * int(value)
            row[2] += float(xpts)
    for pid, made in zip(fts["pid"], fts["made"]):
        row = line.setdefault(int(pid), [0, 0, 0.0, 0, 0])
        row[3] += 1
        row[4] += int(made)
    for side in (0, 1):
        got = sum(row[2] for pid, row in line.items() if side_of[pid] == side)
        if abs(got - expected_fg[side]) > XFG_TIE:
            raise ValueError(f"{gid}: side {side} players' expected FG points {got:.3f} "
                             f"differ from the side's {expected_fg[side]:.3f}")
    players, fallbacks = [], 0
    for pid, (fga, pts, xpts, fta, ftm) in line.items():
        if pid in names:
            name = names[pid]
        else:
            name = pbp_names[pid]
            fallbacks += 1
        players.append([str(pid), name, int(side_of[pid]), fga, pts, round(xpts, 2), fta, ftm])
    players.sort(key=lambda p: (p[2], -(p[4] + p[7]), p[0]))
    return players, fallbacks


def read_game(path: Path, home: int, away: int) -> dict:
    """One cached play-by-play: the final points, each free throw (side, period,
    seconds left, shooter, made), a name for every player it mentions, the
    tricode of each team and the value of every field goal by (event, shooter)."""
    pbp = pd.read_parquet(path, columns=PBP_COLS)
    # 11 cached 2000-01 games (0020000374-389) pad actionType with spaces (the reconstruction gate proves it).
    ft = pbp[pbp["actionType"].str.strip() == "Free Throw"]
    side = np.select([ft["teamId"] == home, ft["teamId"] == away], [0, 1], default=-1)
    named = pbp[(pbp["personId"] > 0) & (pbp["playerName"] != "")]
    fg = pbp[pbp["isFieldGoal"] == 1]
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
        "labels": team_labels(pbp),
        "fg_value": dict(zip(zip(fg["actionNumber"], fg["personId"]), fg["shotValue"])),
    }


def _with_side(df: pd.DataFrame, season: str) -> pd.DataFrame:
    side = np.select([df["team_id"] == df["home_team_id"], df["team_id"] == df["away_team_id"]],
                     [0, 1], default=-1)
    if (side < 0).any():
        raise ValueError(f"{season}: {(side < 0).sum()} shots by a team that is not in its game")
    df["side"] = side
    df["sec"] = np.rint(df["sec"]).astype(int)
    return df


def load_shots(conn, season: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(located, unlocated) shots of the season. Located: with their xFG, shot
    value and coordinates in centimetres. Unlocated: in shots but with no row in
    shots_xfg (the shot-chart feed gave no location); value is NaN where the feed
    gave no shot type either. Both carry the shooter's side (0 home, 1 away)."""
    base = """SELECT s.game_id, s.event_id, s.player_id, s.team_id, s.period,
                     s.seconds_remaining_in_period AS sec, s.shot_made AS made,
                     s.shot_x, s.shot_y, s.shot_type, x.xfg, x.xpts,
                     g.home_team_id, g.away_team_id
              FROM shots s
              {join} JOIN shots_xfg x ON x.game_id = s.game_id AND x.event_id = s.event_id
              JOIN games g ON g.GAME_ID = s.game_id
              WHERE g.season = ?{where}"""
    located = _with_side(pd.read_sql(base.format(join="", where=""), conn, params=(season,)), season)
    located["value"] = located["shot_type"].map(shot_value)
    located["x"] = np.rint(located["shot_x"] * CM_PER_TENTH_FOOT)
    located["y"] = np.rint(located["shot_y"] * CM_PER_TENTH_FOOT)
    unlocated = _with_side(pd.read_sql(
        base.format(join="LEFT", where=" AND x.xfg IS NULL"), conn, params=(season,)), season)
    unlocated["value"] = unlocated["shot_type"].map(lambda t: shot_value(t) if isinstance(t, str) else np.nan)
    chrono = lambda d: d.sort_values(["game_id", "period", "sec", "event_id"],
                                     ascending=[True, True, False, True], kind="stable")
    return chrono(located), unlocated


def export_season(conn, season: str, pbp_files: dict) -> dict:
    """Everything a season publishes except the win-share-dependent fields:
    index rows (win share unrounded), chunk entries by week, and the sums the
    gates read."""
    games = pd.read_sql(
        "SELECT GAME_ID AS game_id, GAME_DATE, home_team_id, away_team_id "
        "FROM games WHERE season = ? ORDER BY GAME_DATE, GAME_ID", conn, params=(season,))
    games["date"] = pd.to_datetime(games["GAME_DATE"]).dt.date
    located, unlocated = load_shots(conn, season)
    rates = make_rates(located)
    shots_by_game = {g: d for g, d in located.groupby("game_id", sort=False)}
    unlocated_by_game = {g: d for g, d in unlocated.groupby("game_id", sort=False)}

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
    out = {"no_pbp": 0, "no_shots": 0, "no_team": 0, "no_value": 0, "side": 0, "mismatch": 0}
    n_unlocated = name_fallbacks = 0

    for g in games.itertuples(index=False):
        gid, home, away = g.game_id, int(g.home_team_id), int(g.away_team_id)
        if gid not in pbp_files:
            out["no_pbp"] += 1
            continue
        if gid not in shots_by_game and gid not in unlocated_by_game:
            out["no_shots"] += 1
            continue
        pbp = read_game(pbp_files[gid], home, away)
        fts = pbp["ft"]
        if (fts["side"] < 0).any():
            out["no_team"] += 1
            continue
        fts["pct"] = fts["pid"].map(ft_pct).fillna(unseen_pct)

        sh = shots_by_game.get(gid, located.iloc[:0])[SHOT_COLS]
        un = unlocated_by_game.get(gid)
        if un is not None:
            # No shot type in the feed: the play-by-play's own shot value, by event and shooter.
            value = [v if v == v else pbp["fg_value"].get((e, p), np.nan)
                     for v, e, p in zip(un["value"], un["event_id"], un["player_id"])]
            if any(v != v for v in value):
                out["no_value"] += 1
                continue
            un = place_unlocated(un.assign(value=np.array(value, dtype=int)), rates)
            sh = pd.concat([sh, un[SHOT_COLS]] if len(sh) else [un[SHOT_COLS]], ignore_index=True)
            sh = sh.sort_values(["period", "sec", "event_id"], ascending=[True, False, True], kind="stable")

        # A player has one side: the team of his shots, which his free throws must agree with.
        side_of = shooter_sides(sh, fts)
        if side_of is None:
            out["side"] += 1
            continue

        tot = side_totals(sh, fts)
        hs, as_ = pbp["points"]
        if (tot[0]["fg"] + tot[0]["ftm"], tot[1]["fg"] + tot[1]["ftm"]) != (hs, as_):
            out["mismatch"] += 1
            continue

        xpts_sum += float(sh["xpts"].sum())
        act_sum += tot[0]["fg"] + tot[1]["fg"]
        n_unlocated += 0 if un is None else len(un)
        share = win_share(sh, fts, seed=zlib.crc32(f"{LEAGUE}{gid}".encode()))
        wins.append(share)
        home_won.append(1.0 if hs > as_ else 0.0 if hs < as_ else 0.5)

        players, fallbacks = player_lines(
            gid, sh, un, fts, lines_by_game.get(gid), side_of, names, pbp["names"],
            {0: tot[0]["xfg"], 1: tot[1]["xfg"]})
        name_fallbacks += fallbacks
        idx = {int(p[0]): i for i, p in enumerate(players)}

        wk = week_key(g.date)
        chunks.setdefault(wk, {})[gid] = {
            "p": players, "s": shot_block(sh, idx), "f": ft_block(fts, idx), "r": officials(meta, gid),
        }
        labels = pbp["labels"]
        rows.append({
            "id": gid, "d": g.date.isoformat(), "wk": wk,
            "h": str(home), "a": str(away),
            "hl": labels.get(home) or TEAM_ABBREV[home], "al": labels.get(away) or TEAM_ABBREV[away],
            "s": [hs, as_],
            "x": [round(tot[0]["xfg"] + tot[0]["xft"], 1), round(tot[1]["xfg"] + tot[1]["xft"], 1)],
            "share": share,
        })

    excluded = sum(out.values())
    return {
        "season": season, "rows": rows, "chunks": chunks, "wins": wins, "home_won": home_won,
        "excluded": excluded, "why": out, "total": len(games), "name_fallbacks": name_fallbacks,
        "unlocated": n_unlocated, "anchor": (xpts_sum - act_sum) / act_sum,
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
        tol = anchor_tolerance(s)
        why = ", ".join(f"{k} {v}" for k, v in r["why"].items() if v)
        print(f"{s}: {len(r['rows'])} games, {r['excluded']} excluded ({frac:.2%})"
              f"{' [' + why + ']' if why else ''}, FG anchor {r['anchor']:+.2%}"
              f"{', unlocated shots in ' + str(r['unlocated']) if r['unlocated'] else ''}"
              f"{', names from pbp ' + str(r['name_fallbacks']) if r['name_fallbacks'] else ''}",
              flush=True)
        if r["excluded"] > left_out_limit(r["total"]):
            failures.append(f"{s}: {r['excluded']} of {r['total']} games left out "
                            f"(limit {left_out_limit(r['total'])})")
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
