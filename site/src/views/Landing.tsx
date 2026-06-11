import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useData } from "../data";
import { int, lastName, signed } from "../lib/format";
import { Delta } from "../components/Delta";
import { useTitle } from "../lib/useTitle";
import SegmentedControl from "../components/SegmentedControl";
import GapArc from "../components/charts/GapArc";
import Beeswarm from "../components/charts/Beeswarm";

export default function Landing() {
  const data = useData();
  useTitle("FTAOE: Free Throw Attempts Over Expected");
  const seasons = data.meta.seasons;
  const latest = seasons[seasons.length - 1];
  const qualify = data.meta.qualifyPossessions;
  const [swarmSeason, setSwarmSeason] = useState(latest);

  const poolBySeason = useMemo(() => {
    const m = new Map<string, typeof data.leaderboard>();
    for (const s of seasons) {
      m.set(
        s,
        data.leaderboard.filter((r) => r.season === s && r.poss >= qualify),
      );
    }
    return m;
  }, [data.leaderboard, seasons, qualify]);

  const heroPool = poolBySeason.get(latest)!;
  const top = useMemo(
    () => [...heroPool].sort((a, b) => b.per100 - a.per100)[0],
    [heroPool],
  );
  const topDetail = data.players[String(top.id)]?.seasons[latest];
  const swarmPool = poolBySeason.get(swarmSeason)!;

  return (
    <div className="mx-auto max-w-4xl px-5 sm:px-8">
      {/* hero */}
      <section className="pt-14 sm:pt-20">
        <p className="font-mono tnum text-xs text-ink-faint">
          {latest} · {int(heroPool.length)} qualified players · shooting fouls
          only
        </p>
        <h1 className="mt-4 max-w-[22ch] font-display text-4xl font-bold leading-[1.05] tracking-tight text-ink sm:text-6xl">
          {top.name} drew {int(Math.round(top.ftaoe))} more free throws than
          the league rate predicts.
        </h1>
        <p className="mt-5 max-w-prose text-base leading-relaxed text-ink-soft sm:text-lg">
          FTAOE counts shooting-foul free throws per 100 possessions against
          the league-average rate. {lastName(top.name)} led the league at{" "}
          <Delta per100={top.per100} className="text-base sm:text-lg" /> per
          100 — {int(top.fta)} attempts where the average player's possessions
          would produce {top.xfta.toFixed(1)}.
        </p>

        {topDetail && (
          <div className="mt-10">
            <GapArc games={topDetail.games} height={250} />
            <p className="mt-2 text-xs text-ink-faint">
              {top.name}, {latest}: cumulative shooting-foul free throws vs the
              league-average pace, game by game.
            </p>
          </div>
        )}

        <div className="mt-10 flex flex-wrap items-center gap-5">
          <Link
            to="/leaderboard"
            className="rounded-md bg-ink px-5 py-2.5 font-display text-sm font-medium text-paper transition-opacity duration-150 hover:opacity-85 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
          >
            Explore the leaderboard
          </Link>
          <Link
            to={`/player/${top.id}?season=${encodeURIComponent(latest)}`}
            className="font-display text-sm font-medium text-ink underline underline-offset-4 transition-colors duration-150 hover:text-ink-soft focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
          >
            See {lastName(top.name)}'s season →
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
            FTAOE — free throw attempts over expected — measures how many
            shooting-foul free throws a player draws per 100 possessions,
            compared with the league-average rate (
            <span className="font-mono tnum">
              {data.meta.leagueRatePer100.toFixed(1)}
            </span>{" "}
            per 100 across the three seasons).
          </p>
          <p>
            <strong className="font-semibold">What counts:</strong> shooting
            fouls only — and-1s and fouled misses. Free throws from the
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
            prove anything about referees — that stays an open question.{" "}
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

      {/* league distribution */}
      <section className="mt-20 border-t border-line pt-12 sm:mt-28">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h2 className="font-display text-2xl font-semibold tracking-tight text-ink sm:text-3xl">
              Every qualified player
            </h2>
            <p className="mt-2 text-sm text-ink-soft">
              {int(swarmPool.length)} players with ≥ {int(qualify)}{" "}
              possessions, {swarmSeason}. Tap a dot.
            </p>
          </div>
          <SegmentedControl
            ariaLabel="Season"
            options={seasons.map((s) => ({ value: s, label: s }))}
            value={swarmSeason}
            onChange={setSwarmSeason}
          />
        </div>
        <Beeswarm
          className="mt-8"
          players={swarmPool.map((r) => ({
            id: r.id,
            name: r.name,
            per100: r.per100,
          }))}
          season={swarmSeason}
        />
        <p className="mt-6 text-sm text-ink-soft">
          The spread is enormous: from{" "}
          <span className="font-mono tnum">
            {signed(Math.min(...swarmPool.map((r) => r.per100)), 1)}
          </span>{" "}
          to{" "}
          <span className="font-mono tnum">
            {signed(Math.max(...swarmPool.map((r) => r.per100)), 1)}
          </span>{" "}
          free throws per 100 possessions against the same league baseline.
        </p>
      </section>
    </div>
  );
}
