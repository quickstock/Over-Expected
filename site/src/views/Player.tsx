import { useMemo, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { useData, usePlayerChunk } from "../data";
import { useTitle } from "../lib/useTitle";
import { divergingText } from "../lib/color";
import { int, ordinal, signed } from "../lib/format";
import { useCountUp } from "../lib/useCountUp";
import SegmentedControl from "../components/SegmentedControl";
import GapArc from "../components/charts/GapArc";
import FormStrip from "../components/charts/FormStrip";
import CourtZones from "../components/charts/CourtZones";

const FORM_WINDOWS = ["5", "10", "15", "20"];

function NotFound({ qualify }: { qualify: number }) {
  return (
    <div className="mx-auto max-w-xl px-5 py-28 text-center sm:px-8">
      <p className="font-display text-2xl font-semibold text-ink">
        No qualified season for this player.
      </p>
      <p className="mt-3 text-sm leading-relaxed text-ink-soft">
        Player pages require at least {int(qualify)} possessions in a season —
        below that, per-possession rates are too unstable to present.
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
              Trailing {formWindow}-game FTAOE per 100 possessions — the
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

      {/* shot diet */}
      <section className="mt-14">
        <h2 className="font-display text-xl font-semibold tracking-tight text-ink sm:text-2xl">
          Where he attacks
        </h2>
        <p className="mt-1.5 text-sm text-ink-soft">
          Charged field-goal attempts by zone, {season}.
        </p>
        {detail ? (
          <CourtZones zones={detail.zones} className="mt-6 max-w-[520px]" />
        ) : chunk.status === "error" ? null : (
          <div
            className="mt-6 aspect-[500/434] max-w-[520px] animate-pulse rounded bg-wash"
            aria-busy="true"
          />
        )}
      </section>

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
