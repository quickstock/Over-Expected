import { useMemo } from "react";
import { Link } from "react-router-dom";
import { useData } from "../data";
import { useTitle } from "../lib/useTitle";
import { int, lastName, signed } from "../lib/format";
import { Delta } from "../components/Delta";
import RateSteps from "../components/story/RateSteps";
import SlopeChart from "../components/story/SlopeChart";
import type { SlopePair } from "../components/story/SlopeChart";

const BEFORE = "2020-21";
const AFTER = "2021-22";

/**
 * The 2021-22 interpretive change on non-basketball moves, measured
 * with FTAOE. Everything on this page is computed from the shipped
 * data; the highlighted players are simply the largest movers.
 */
export default function Story() {
  const data = useData();
  useTitle("The crackdown, measured · FTAOE");

  const { pairs, fallers, riser } = useMemo(() => {
    const a = new Map(
      data.leaderboard
        .filter((r) => r.season === BEFORE && r.pct !== null)
        .map((r) => [r.id, r]),
    );
    const pairs: SlopePair[] = [];
    for (const r of data.leaderboard) {
      if (r.season !== AFTER || r.pct === null) continue;
      const prev = a.get(r.id);
      if (!prev) continue;
      pairs.push({
        id: r.id,
        name: r.name,
        before: prev.per100,
        after: r.per100,
      });
    }
    const byDelta = [...pairs].sort(
      (p, q) => p.after - p.before - (q.after - q.before),
    );
    return {
      pairs,
      fallers: byDelta.slice(0, 5),
      riser: byDelta[byDelta.length - 1],
    };
  }, [data]);

  const f0 = fallers[0];
  const pairR = data.meta.reliability.yoyPairs.find((p) =>
    p.pair.startsWith(BEFORE),
  );

  return (
    <article className="mx-auto max-w-2xl px-5 py-12 sm:px-8 sm:py-16">
      <p className="font-mono tnum text-xs text-ink-faint">
        From the data · the {AFTER} interpretive change
      </p>
      <h1 className="mt-4 font-display text-4xl font-bold leading-[1.05] tracking-tight text-ink sm:text-6xl">
        The crackdown, measured.
      </h1>
      <p className="mt-5 text-base leading-relaxed text-ink-soft sm:text-lg">
        Before the {AFTER} season, the NBA told its officials to stop
        rewarding "non-basketball moves": launching into defenders, abrupt
        sideways lunges, kicking a leg out on a jumper. The stated target
        was foul-baiting. Six seasons of FTAOE show what actually changed,
        and it isn't where most people look.
      </p>

      <h2 className="mt-14 font-display text-xl font-semibold tracking-tight text-ink sm:text-2xl">
        The league barely moved
      </h2>
      <p className="mt-3 text-[15px] leading-relaxed sm:text-base">
        The league's shooting-foul rate dipped from{" "}
        <span className="font-mono tnum">
          {data.meta.leagueRateBySeason[BEFORE].toFixed(1)}
        </span>{" "}
        to{" "}
        <span className="font-mono tnum">
          {data.meta.leagueRateBySeason[AFTER].toFixed(1)}
        </span>{" "}
        free throws per 100 possessions, a quarter of a free throw, and was
        higher than ever two seasons later. If the crackdown had been a
        league-wide whistle change, this chart would show it. It doesn't.
      </p>
      <RateSteps
        className="mt-6"
        rates={data.meta.leagueRateBySeason}
        annotate={AFTER}
        annotation="the memo season"
      />

      <h2 className="mt-14 font-display text-xl font-semibold tracking-tight text-ink sm:text-2xl">
        Specific games got repriced
      </h2>
      <p className="mt-3 text-[15px] leading-relaxed sm:text-base">
        Among the {int(pairs.length)} players with qualified seasons on both
        sides of the memo, the change was surgical. {f0.name} fell{" "}
        <span className="font-mono tnum">
          {signed(f0.after - f0.before, 1)}
        </span>{" "}
        per 100, from <Delta per100={f0.before} className="text-[15px] sm:text-base" /> (elite)
        to <Delta per100={f0.after} className="text-[15px] sm:text-base" /> (below league
        average) in one summer.{" "}
        {fallers
          .slice(1, 4)
          .map((f) => lastName(f.name))
          .join(", ")}{" "}
        gave back five to nine points each. The moves the memo described
        were the moves their free throws leaned on.
      </p>
      <SlopeChart
        className="mt-6"
        pairs={pairs}
        highlight={[...fallers.map((f) => f.id), riser.id]}
        beforeLabel={BEFORE}
        afterLabel={AFTER}
      />
      <p className="mt-2 text-xs leading-relaxed text-ink-faint">
        FTAOE per 100 possessions, every player qualified in both seasons.
        Colored lines are the five largest falls and the largest rise;
        color encodes the change. Tap a line for the player page. Each
        season is measured against its own league average, so these are
        moves in rank, not artifacts of the league-wide rate.
      </p>

      <h2 className="mt-14 font-display text-xl font-semibold tracking-tight text-ink sm:text-2xl">
        The skill survived
      </h2>
      <p className="mt-3 text-[15px] leading-relaxed sm:text-base">
        Here's the part that makes FTAOE worth trusting: across the rule
        change, the ordering of players held at{" "}
        <span className="font-mono tnum">r = {pairR?.r.toFixed(2)}</span>{" "}
        ({int(pairR?.n ?? 0)} repeat players), right in line with every
        other pair of seasons. Foul-drawing stayed a stable skill; the
        league repriced one way of expressing it. A handful of players paid
        almost the entire cost of the memo, and the data can say that
        plainly without claiming anything about any official: enforcement
        standards are set by the league, and the change was announced in
        advance.
      </p>

      <div className="mt-14 flex flex-wrap items-center gap-5 border-t border-line pt-8">
        <Link
          to="/leaderboard?season=2021-22"
          className="rounded-md bg-ink px-5 py-2.5 font-display text-sm font-medium text-paper transition-opacity duration-150 hover:opacity-85 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
        >
          The {AFTER} leaderboard
        </Link>
        <Link
          to="/methodology"
          className="font-display text-sm font-medium text-ink underline underline-offset-4 transition-colors duration-150 hover:text-ink-soft focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
        >
          How FTAOE is measured →
        </Link>
      </div>
    </article>
  );
}
