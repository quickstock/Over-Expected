import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useData, usePlayerChunk } from "../data";
import type { LeaderboardRow } from "../types";
import { int, lastName, ordinal } from "../lib/format";
import { Delta } from "../components/Delta";
import { useTitle } from "../lib/useTitle";
import SegmentedControl from "../components/SegmentedControl";
import GapArc from "../components/charts/GapArc";
import Beeswarm from "../components/charts/Beeswarm";

const POSITIONS = ["All", "Guard", "Forward", "Center"];

function seasonShort(s: string) {
  return `'${s.slice(2, 4)}-${s.slice(5)}`;
}

/** Compact extreme-player profile used in "The largest gaps". */
function ExtremeCard({
  row,
  tag,
}: {
  row: LeaderboardRow;
  tag: string;
}) {
  return (
    <Link
      to={`/player/${row.id}?season=${encodeURIComponent(row.season)}`}
      className="group flex flex-col gap-1.5 border-t border-line pt-4 transition-colors duration-150 hover:bg-wash focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
    >
      <span className="font-display text-[11px] font-medium uppercase tracking-wider text-ink-faint">
        {tag}
      </span>
      <span className="flex flex-wrap items-baseline gap-x-3">
        <span className="font-display text-2xl font-semibold text-ink group-hover:underline group-hover:underline-offset-4">
          {row.name}
        </span>
        <Delta per100={row.per100} className="text-2xl" />
      </span>
      <span className="font-mono tnum text-sm text-ink-soft">
        per 100 · {ordinal(Math.floor(row.pct ?? 0))} %ile · {int(row.poss)}{" "}
        poss
      </span>
    </Link>
  );
}

export default function Landing() {
  const data = useData();
  useTitle("FTAOE: Free Throw Attempts Over Expected");
  const seasons = data.meta.seasons;
  const latest = seasons[seasons.length - 1];
  const qualify = data.meta.qualifyPossessions;

  const [swarmSeason, setSwarmSeason] = useState(latest);
  const [swarmPos, setSwarmPos] = useState("All");
  const [query, setQuery] = useState("");
  const [found, setFound] = useState<LeaderboardRow | null>(null);

  const poolBySeason = useMemo(() => {
    const m = new Map<string, LeaderboardRow[]>();
    for (const s of seasons) {
      m.set(
        s,
        data.leaderboard.filter((r) => r.season === s && r.poss >= qualify),
      );
    }
    return m;
  }, [data.leaderboard, seasons, qualify]);

  const seasonPool = poolBySeason.get(swarmSeason)!;
  const swarmPool = useMemo(
    () =>
      swarmPos === "All"
        ? seasonPool
        : seasonPool.filter((r) => r.pos === swarmPos),
    [seasonPool, swarmPos],
  );

  const suggestions = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (q.length < 2) return [];
    return seasonPool
      .filter((r) => r.name.toLowerCase().includes(q))
      .sort((a, b) => b.poss - a.poss)
      .slice(0, 6);
  }, [query, seasonPool]);

  const heroPool = poolBySeason.get(latest)!;
  const sorted = useMemo(
    () => [...heroPool].sort((a, b) => b.per100 - a.per100),
    [heroPool],
  );
  const top = sorted[0];
  const bottom = sorted[sorted.length - 1];
  const latestChunk = usePlayerChunk(latest);
  const topDetail =
    latestChunk.status === "ready"
      ? latestChunk.chunk[String(top.id)]
      : undefined;

  const swarmMin = Math.min(...swarmPool.map((r) => r.per100));
  const swarmMax = Math.max(...swarmPool.map((r) => r.per100));

  return (
    <div className="mx-auto max-w-4xl px-5 sm:px-8">
      {/* hero: the statistic, not a player */}
      <section className="pt-14 sm:pt-20">
        <p className="font-mono tnum text-xs text-ink-faint">
          FTAOE · {seasonShort(seasons[0])} to {seasonShort(latest)} ·
          shooting fouls only
        </p>
        <h1 className="mt-4 font-display text-5xl font-bold leading-[1.02] tracking-tight text-ink sm:text-7xl">
          The free-throw gap.
        </h1>
        <p className="mt-5 max-w-prose text-base leading-relaxed text-ink-soft sm:text-lg">
          Some players live at the line; some never get there. FTAOE measures
          the gap: shooting-foul free throws drawn per 100 possessions,
          against the league-average rate. In {swarmSeason} it ran from{" "}
          <Delta per100={swarmMin} className="text-base sm:text-lg" /> to{" "}
          <Delta per100={swarmMax} className="text-base sm:text-lg" /> per
          100.
        </p>

        {/* the league, adjustable */}
        <div className="mt-10 flex flex-wrap items-center gap-x-4 gap-y-3">
          <SegmentedControl
            ariaLabel="Season"
            options={seasons.map((s) => ({
              value: s,
              label: s,
              shortLabel: seasonShort(s),
            }))}
            value={swarmSeason}
            onChange={(s) => {
              setSwarmSeason(s);
              setFound(null);
              setQuery("");
            }}
          />
          <SegmentedControl
            ariaLabel="Position"
            options={POSITIONS.map((p) => ({
              value: p,
              label: p === "All" ? "All" : p.slice(0, 1),
            }))}
            value={swarmPos}
            onChange={setSwarmPos}
          />
          <div className="relative">
            <input
              type="search"
              value={query}
              onChange={(e) => {
                setQuery(e.target.value);
                setFound(null);
              }}
              placeholder="Find a player"
              aria-label="Find a player"
              className="w-40 rounded-md border border-line bg-paper px-3 py-1.5 font-display text-[13px] text-ink placeholder:text-ink-faint focus:border-ink-faint focus:outline-none focus-visible:outline-2 focus-visible:-outline-offset-1 focus-visible:outline-ink"
            />
            {suggestions.length > 0 && !found && (
              <ul className="absolute z-20 mt-1 w-56 overflow-hidden rounded-md border border-line bg-paper shadow-sm">
                {suggestions.map((r) => (
                  <li key={r.id}>
                    <button
                      type="button"
                      onClick={() => {
                        setFound(r);
                        setQuery(r.name);
                      }}
                      className="flex w-full items-baseline justify-between px-3 py-2 text-left font-display text-[13px] text-ink transition-colors duration-100 hover:bg-wash focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-ink"
                    >
                      <span>{r.name}</span>
                      <Delta per100={r.per100} className="text-xs" />
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>

        <Beeswarm
          className="mt-6"
          players={swarmPool.map((r) => ({
            id: r.id,
            name: r.name,
            per100: r.per100,
          }))}
          season={swarmSeason}
          highlightIds={found ? [found.id] : []}
        />
        <p className="mt-2 text-xs text-ink-faint">
          {int(swarmPool.length)} players with ≥ {int(qualify)} possessions,{" "}
          {swarmSeason}
          {swarmPos !== "All" ? `, ${swarmPos.toLowerCase()}s` : ""}. Every
          dot is a player. Tap one.
        </p>

        <div className="mt-10 flex flex-wrap items-center gap-5">
          <Link
            to="/leaderboard"
            className="rounded-md bg-ink px-5 py-2.5 font-display text-sm font-medium text-paper transition-opacity duration-150 hover:opacity-85 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
          >
            Explore the leaderboard
          </Link>
          <Link
            to="/methodology"
            className="font-display text-sm font-medium text-ink underline underline-offset-4 transition-colors duration-150 hover:text-ink-soft focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
          >
            How it's measured →
          </Link>
        </div>
      </section>

      {/* explainer */}
      <section className="mt-20 border-t border-line pt-12 sm:mt-28">
        <h2 className="font-display text-2xl font-semibold tracking-tight text-ink sm:text-3xl">
          What this measures
        </h2>
        <div className="mt-6 max-w-prose space-y-4 text-[15px] leading-relaxed text-ink sm:text-base">
          <p>
            FTAOE (free throw attempts over expected) measures how many
            shooting-foul free throws a player draws per 100 possessions,
            compared with the league-average rate (
            <span className="font-mono tnum">
              {data.meta.leagueRatePer100.toFixed(1)}
            </span>{" "}
            per 100 across {int(seasons.length)} seasons).
          </p>
          <p>
            <strong className="font-semibold">What counts:</strong> shooting
            fouls only: and-1s and fouled misses. Free throws from the
            bonus, technicals, flagrants, and off-ball fouls are excluded.
          </p>
          <p>
            <strong className="font-semibold">Why per possession:</strong> a
            fouled miss isn't a charged field-goal attempt and has no shot
            location, so any per-shot rate quietly drops the exact plays this
            stat is about. The possession is the honest unit.
          </p>
          <p>
            <strong className="font-semibold">
              What it does and doesn't say:
            </strong>{" "}
            the number blends playstyle, contact-seeking skill, and
            officiating. It does not isolate any of them, and it does not
            prove anything about referees; that stays an open question.{" "}
            <Link
              to="/methodology"
              className="underline underline-offset-2 transition-colors duration-150 hover:text-ink-soft focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
            >
              Full methodology
            </Link>
            .
          </p>
        </div>
      </section>

      {/* the largest gaps */}
      <section className="mt-20 border-t border-line pt-12 sm:mt-28">
        <h2 className="font-display text-2xl font-semibold tracking-tight text-ink sm:text-3xl">
          The largest gaps, {latest}
        </h2>
        <div className="mt-8 grid gap-6 sm:grid-cols-2">
          <ExtremeCard row={top} tag="most above the league rate" />
          <ExtremeCard row={bottom} tag="most below the league rate" />
        </div>
        <div className="mt-10">
          {topDetail ? (
            <GapArc games={topDetail.games} height={250} />
          ) : (
            <div className="h-[250px] animate-pulse rounded bg-wash" aria-busy="true" />
          )}
          <p className="mt-2 text-xs text-ink-faint">
            {top.name}, {latest}: cumulative shooting-foul free throws vs the
            league-average pace: {int(top.fta)} attempts where the average
            player's possessions would produce {top.xfta.toFixed(1)}.{" "}
            <Link
              to={`/player/${top.id}?season=${encodeURIComponent(latest)}`}
              className="underline underline-offset-2 transition-colors duration-150 hover:text-ink"
            >
              {lastName(top.name)}'s page →
            </Link>
          </p>
        </div>
      </section>
    </div>
  );
}
