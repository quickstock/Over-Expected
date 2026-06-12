import { useMemo, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { useData, usePlayerChunk } from "../data";
import { useTitle } from "../lib/useTitle";
import { divergingText } from "../lib/color";
import { int, ordinal, signed } from "../lib/format";
import { useCountUp } from "../lib/useCountUp";
import { Delta } from "../components/Delta";
import SegmentedControl from "../components/SegmentedControl";
import GapArc from "../components/charts/GapArc";
import FormStrip from "../components/charts/FormStrip";
import CourtZones from "../components/charts/CourtZones";
import FoulLedger from "../components/player/FoulLedger";
import PercentileSliders from "../components/player/PercentileSliders";
import CareerStrip from "../components/player/CareerStrip";

const FORM_WINDOWS = ["5", "10", "15", "20"];

function NotFound({ qualify }: { qualify: number }) {
  return (
    <div className="mx-auto max-w-xl px-5 py-28 text-center sm:px-8">
      <p className="font-display text-2xl font-semibold text-ink">
        No qualified season for this player.
      </p>
      <p className="mt-3 text-sm leading-relaxed text-ink-soft">
        Player pages require at least {int(qualify)} possessions in a season.
        Below that, per-possession rates are too unstable to present.
      </p>
      <Link
        to="/leaderboard"
        className="mt-8 inline-block rounded-md bg-ink px-5 py-2.5 font-display text-sm font-medium text-paper transition-opacity duration-150 hover:opacity-85 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
      >
        Back to the leaderboard
      </Link>
    </div>
  );
}

function Stat({
  value,
  label,
  sub,
  delay,
}: {
  value: React.ReactNode;
  label: string;
  sub?: string;
  delay: number;
}) {
  return (
    <div
      className="flex translate-y-0 flex-col gap-1.5 px-1 py-4 opacity-100 transition-[opacity,transform] duration-500 starting:translate-y-2 starting:opacity-0 sm:py-1"
      style={{ transitionDelay: `${delay}ms` }}
    >
      <span className="font-display text-[11px] font-medium uppercase tracking-wider text-ink-faint">
        {label}
      </span>
      <span className="font-mono tnum text-3xl text-ink sm:text-4xl">
        {value}
      </span>
      {sub && <span className="text-xs text-ink-soft">{sub}</span>}
    </div>
  );
}

export default function Player() {
  const data = useData();
  const { id } = useParams();
  const [params, setParams] = useSearchParams();
  const [formWindow, setFormWindow] = useState("10");
  const [courtMode, setCourtMode] = useState("attempts");

  const qualify = data.meta.qualifyPossessions;

  // Qualified player-season rows for this id, in league season order.
  const rows = useMemo(() => {
    const pid = Number(id);
    const mine = data.leaderboard.filter(
      (r) => r.id === pid && r.pct !== null,
    );
    return data.meta.seasons
      .map((s) => mine.find((r) => r.season === s))
      .filter((r): r is NonNullable<typeof r> => r !== undefined);
  }, [data, id]);

  // Career pooling over qualified seasons (client-side; all rows ship in
  // the core JSON). Pool for the career percentile: >= 1000 career poss.
  const career = useMemo(() => {
    const byId = new Map<
      number,
      { poss: number; ftaoe: number; fta: number; xfta: number; n: number }
    >();
    for (const r of data.leaderboard) {
      if (r.pct === null) continue;
      const c =
        byId.get(r.id) ?? { poss: 0, ftaoe: 0, fta: 0, xfta: 0, n: 0 };
      c.poss += r.poss;
      c.ftaoe += r.ftaoe;
      c.fta += r.fta;
      c.xfta += r.xfta;
      c.n += 1;
      byId.set(r.id, c);
    }
    const pool: number[] = [];
    for (const c of byId.values()) {
      if (c.poss >= 1000) pool.push((c.ftaoe / c.poss) * 100);
    }
    pool.sort((a, b) => a - b);
    return { byId, pool };
  }, [data.leaderboard]);

  const seasons = rows.map((r) => r.season);
  const requested = params.get("season");
  const season =
    requested && seasons.includes(requested)
      ? requested
      : seasons[seasons.length - 1] ?? null;
  const row = rows.find((r) => r.season === season);

  const chunk = usePlayerChunk(season);
  useTitle(row ? `${row.name} · FTAOE` : "FTAOE");
  const animatedPer100 = useCountUp(row?.per100 ?? 0);

  if (!row || !season) return <NotFound qualify={qualify} />;

  const detail =
    chunk.status === "ready" ? chunk.chunk[String(row.id)] : undefined;
  const fouls = detail?.fouls;

  const myCareer = career.byId.get(Number(id));
  const careerPer100 = myCareer ? (myCareer.ftaoe / myCareer.poss) * 100 : null;
  const careerPct =
    myCareer && myCareer.poss >= 1000 && career.pool.length > 0 && careerPer100 !== null
      ? (career.pool.filter((v) => v <= careerPer100).length /
          career.pool.length) *
        100
      : null;

  const setSeason = (s: string) => {
    const next = new URLSearchParams(params);
    next.set("season", s);
    setParams(next);
  };

  return (
    <div className="mx-auto max-w-4xl px-5 py-10 sm:px-8 sm:py-14">
      <Link
        to={`/leaderboard?season=${encodeURIComponent(season)}`}
        className="font-display text-sm text-ink-soft transition-colors duration-150 hover:text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
      >
        ← Leaderboard
      </Link>

      <header className="mt-6">
        <h1 className="font-display text-4xl font-bold tracking-tight text-ink sm:text-6xl">
          {row.name}
        </h1>
        <p className="mt-3 text-sm text-ink-soft">
          {row.teams.join(" → ")}
          {row.pos ? ` · ${row.pos}` : ""} · {int(row.poss)} possessions
        </p>
        {seasons.length > 1 ? (
          <SegmentedControl
            ariaLabel="Season"
            className="mt-5"
            options={seasons.map((s) => ({
              value: s,
              label: s,
              shortLabel: `'${s.slice(2, 4)}-${s.slice(5)}`,
            }))}
            value={season}
            onChange={setSeason}
          />
        ) : (
          <p className="mt-5 font-display text-[13px] font-medium text-ink-soft">
            {season}
          </p>
        )}
      </header>

      {/* stat band */}
      <section className="mt-10 grid grid-cols-2 divide-line border-y border-line py-2 max-sm:[&>*:nth-child(odd)]:border-r max-sm:[&>*:nth-child(-n+2)]:border-b sm:grid-cols-4 sm:divide-x sm:py-5">
        <Stat
          delay={0}
          value={
            <span
              className="text-4xl sm:text-5xl"
              style={{ color: divergingText(row.per100) }}
            >
              {signed(animatedPer100, 1)}
            </span>
          }
          label="FTAOE per 100 poss"
        />
        <Stat
          delay={60}
          value={
            row.pct !== null ? (
              <>
                {ordinal(Math.floor(row.pct))}
                <span className="text-xl text-ink-faint"> %ile</span>
              </>
            ) : (
              "—"
            )
          }
          label="Percentile"
          sub={`among qualified, ${season}`}
        />
        <Stat
          delay={120}
          value={
            <>
              {int(row.fta)}
              <span className="text-xl text-ink-faint"> / {row.xfta.toFixed(1)}</span>
            </>
          }
          label="Actual / expected FTA"
          sub={`league rate: ${data.meta.leagueRateBySeason[season].toFixed(1)} per 100`}
        />
        <Stat
          delay={180}
          value={
            <span style={{ color: divergingText(row.per100) }}>
              {signed(row.ftaoe, 1)}
            </span>
          }
          label="Extra FTA vs league"
        />
      </section>

      {/* where he ranks */}
      <section className="mt-6 border-b border-line-soft pb-4">
        <h2 className="font-display text-[11px] font-medium uppercase tracking-wider text-ink-faint">
          Where he ranks
        </h2>
        <PercentileSliders
          className="mt-1"
          rows={[
            {
              label: `FTAOE/100, ${season}`,
              per100: row.per100,
              pct: row.pct,
            },
            {
              label: "Style-adjusted",
              per100: row.sper100 ?? 0,
              pct: row.sper100 !== null ? row.spct : null,
              note: (
                <>
                  Above what his attack profile (drives, paint and post
                  touches) predicts; a different question than the headline
                  number.{" "}
                  <Link
                    to="/methodology"
                    className="underline underline-offset-2 transition-colors duration-150 hover:text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
                  >
                    How it differs
                  </Link>
                  .
                </>
              ),
            },
            {
              label: `Career, ${myCareer?.n ?? 0} seasons`,
              per100: careerPer100 ?? 0,
              pct: careerPct,
              note: "Career rank among players with at least 1,000 possessions across qualified seasons.",
            },
          ]}
        />
      </section>

      {/* the gap */}
      <section className="mt-14">
        <h2 className="font-display text-xl font-semibold tracking-tight text-ink sm:text-2xl">
          The season, drawn as a gap
        </h2>
        <p className="mt-1.5 text-sm text-ink-soft">
          Cumulative shooting-foul free throws vs the league-average pace,
          game by game.
        </p>
        {detail ? (
          <GapArc games={detail.games} className="mt-6" />
        ) : chunk.status === "error" ? (
          <p className="mt-6 rounded border border-line-soft bg-wash px-4 py-8 text-center text-sm text-ink-faint">
            The per-game series failed to load. Refresh to retry.
          </p>
        ) : (
          <div className="mt-6 h-[280px] animate-pulse rounded bg-wash" aria-busy="true" />
        )}
      </section>

      {/* form */}
      <section className="mt-14">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h2 className="font-display text-xl font-semibold tracking-tight text-ink sm:text-2xl">
              Form
            </h2>
            <p className="mt-1.5 text-sm text-ink-soft">
              Trailing {formWindow}-game FTAOE per 100 possessions: the
              leaderboard's unit, watched move through the season.
            </p>
          </div>
          <SegmentedControl
            ariaLabel="Window size in games"
            options={FORM_WINDOWS.map((w) => ({ value: w, label: `${w} gm` }))}
            value={formWindow}
            onChange={setFormWindow}
          />
        </div>
        {detail ? (
          <FormStrip
            games={detail.games}
            window={Number(formWindow)}
            className="mt-6"
          />
        ) : chunk.status === "error" ? null : (
          <div className="mt-6 h-[200px] animate-pulse rounded bg-wash" aria-busy="true" />
        )}
      </section>

      {/* where it happens */}
      <section className="mt-14">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h2 className="font-display text-xl font-semibold tracking-tight text-ink sm:text-2xl">
              Where it happens
            </h2>
            <p className="mt-1.5 text-sm text-ink-soft">
              {fouls && courtMode === "fouls"
                ? `And-1s by zone, ${season}: the only shooting fouls with an official location.`
                : `Charged field-goal attempts by zone, ${season}.`}
            </p>
          </div>
          {fouls && fouls.located > 0 && (
            <SegmentedControl
              ariaLabel="Court view"
              options={[
                { value: "attempts", label: "All attempts" },
                { value: "fouls", label: "And-1s" },
              ]}
              value={courtMode}
              onChange={setCourtMode}
            />
          )}
        </div>
        {detail ? (
          <CourtZones
            zones={
              fouls && courtMode === "fouls" ? fouls.zones : detail.zones
            }
            footnote={
              fouls && courtMode === "fouls"
                ? `${int(fouls.located)} of ${int(fouls.and1)} and-1s have an official shot location. Fouled misses are itemized below the court, never placed.`
                : undefined
            }
            className="mt-6 max-w-[520px]"
          />
        ) : chunk.status === "error" ? null : (
          <div
            className="mt-6 aspect-[500/434] max-w-[520px] animate-pulse rounded bg-wash"
            aria-busy="true"
          />
        )}
      </section>

      {/* the ledger */}
      {fouls && (
        <section className="mt-14">
          <h2 className="font-display text-xl font-semibold tracking-tight text-ink sm:text-2xl">
            Every free throw, accounted for
          </h2>
          <p className="mt-1.5 text-sm text-ink-soft">
            And-1s award one free throw, fouled 2-pt misses two, fouled 3-pt
            misses three. The column sums to the season total exactly.
          </p>
          <FoulLedger fouls={fouls} fta={row.fta} className="mt-6" />
        </section>
      )}

      {/* career */}
      {rows.length > 1 && myCareer && careerPer100 !== null && (
        <section className="mt-14">
          <h2 className="font-display text-xl font-semibold tracking-tight text-ink sm:text-2xl">
            Career
          </h2>
          <p className="mt-1.5 text-sm text-ink-soft">
            {int(myCareer.fta)} FTA vs {myCareer.xfta.toFixed(1)} expected
            over {int(myCareer.poss)} possessions across {int(myCareer.n)}{" "}
            qualified seasons:{" "}
            <Delta per100={careerPer100} className="text-sm" /> per 100.
            Tap a season.
          </p>
          <CareerStrip
            rows={rows}
            activeSeason={season}
            onSelect={setSeason}
            className="mt-4 max-w-2xl"
          />
        </section>
      )}

      <p className="mt-16 border-t border-line pt-6">
        <Link
          to={`/leaderboard?season=${encodeURIComponent(season)}`}
          className="font-display text-sm font-medium text-ink underline underline-offset-4 transition-colors duration-150 hover:text-ink-soft focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
        >
          See everyone →
        </Link>
      </p>
    </div>
  );
}
