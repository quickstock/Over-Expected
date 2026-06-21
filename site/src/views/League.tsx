import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useData } from "../data";
import type { TeamRow } from "../types";
import { useTitle } from "../lib/useTitle";
import { divergingText } from "../lib/color";
import { signed } from "../lib/format";
import { useMeasure } from "../lib/useMeasure";
import { useRevealed } from "../lib/useRevealed";
import SegmentedControl from "../components/SegmentedControl";
import TeamScatter from "../components/charts/TeamScatter";

const WARM = "oklch(0.58 0.17 38)";

/**
 * League shooting-foul rate per 100 by season: the foul environment over time.
 * The 2021-22 crackdown is marked warm. The line draws in on first view.
 */
function LeagueTrend({
  seasons,
  rates,
}: {
  seasons: string[];
  rates: Record<string, number>;
}) {
  const [wrapRef, width] = useMeasure<HTMLDivElement>();
  const revealed = useRevealed(wrapRef);
  const pts = seasons.filter((s) => rates[s] != null).map((s) => ({ s, v: rates[s] }));
  const height = 210;
  const pad = { top: 26, right: 16, bottom: 32, left: 16 };
  const innerW = Math.max(40, width - pad.left - pad.right);
  const innerH = height - pad.top - pad.bottom;
  const vals = pts.map((p) => p.v);
  const lo = Math.min(...vals) - 0.5;
  const hi = Math.max(...vals) + 0.5;
  const x = (i: number) => pad.left + (i / Math.max(1, pts.length - 1)) * innerW;
  const y = (v: number) => pad.top + innerH - ((v - lo) / (hi - lo)) * innerH;
  const path = pts
    .map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)} ${y(p.v).toFixed(1)}`)
    .join("");

  return (
    <div ref={wrapRef} className="relative">
      {width > 0 && (
        <svg
          width={width}
          height={height}
          role="img"
          aria-label={`League shooting-foul free throws per 100 by season, from ${pts[0].v.toFixed(1)} to ${pts[pts.length - 1].v.toFixed(1)}.`}
        >
          <path
            d={path}
            fill="none"
            stroke="var(--color-ink)"
            strokeWidth={2}
            strokeLinejoin="round"
            strokeLinecap="round"
            pathLength={1}
            style={{
              strokeDasharray: 1,
              strokeDashoffset: revealed ? 0 : 1,
              transition: "stroke-dashoffset 900ms var(--ease-out-strong)",
            }}
          />
          {pts.map((p, i) => {
            const crack = p.s === "2021-22";
            return (
              <g
                key={p.s}
                style={{
                  opacity: revealed ? 1 : 0,
                  transition: `opacity 360ms ease ${250 + i * 60}ms`,
                }}
              >
                <circle
                  cx={x(i)}
                  cy={y(p.v)}
                  r={crack ? 5 : 3.5}
                  fill={crack ? WARM : "var(--color-ink)"}
                  stroke="var(--color-paper)"
                  strokeWidth={crack ? 1.75 : 1}
                />
                <text
                  x={x(i)}
                  y={y(p.v) - 12}
                  textAnchor="middle"
                  fontSize={11}
                  fontWeight={crack ? 700 : 400}
                  className="font-mono tnum"
                  fill={crack ? WARM : "var(--color-ink)"}
                >
                  {p.v.toFixed(1)}
                </text>
                <text
                  x={x(i)}
                  y={height - 10}
                  textAnchor="middle"
                  fontSize={10}
                  className="font-mono"
                  fill={crack ? WARM : "var(--color-ink-faint)"}
                >
                  '{p.s.slice(2, 4)}-{p.s.slice(5)}
                </text>
                {crack && (
                  <text
                    x={x(i)}
                    y={height - 22}
                    textAnchor="middle"
                    fontSize={9.5}
                    className="font-display"
                    fill={WARM}
                  >
                    crackdown
                  </text>
                )}
              </g>
            );
          })}
        </svg>
      )}
    </div>
  );
}

export default function League() {
  const data = useData();
  useTitle("League context · Over Expected");
  const seasons = data.meta.seasons;
  const [season, setSeason] = useState(data.meta.defaultSeason);
  const [side, setSide] = useState<"drawn" | "conceded">("drawn");

  const teams = useMemo(
    () => [...(data.teams[season] ?? [])].sort((a, b) => b[side] - a[side]),
    [data.teams, season, side],
  );

  return (
    <div className="mx-auto max-w-3xl px-5 py-12 sm:px-8 sm:py-16">
      <h1 className="font-display text-3xl font-bold tracking-tight text-balance text-ink sm:text-5xl">
        League context
      </h1>
      <p className="mt-3 max-w-prose text-sm leading-relaxed text-ink-soft sm:text-base">
        Is it the player, or the situation around him? Shooting fouls drawn and
        conceded by team, the context a player's foul-drawing number rides on.
      </p>

      <SegmentedControl
        ariaLabel="Season"
        className="mt-8"
        options={seasons.map((s) => ({
          value: s,
          label: s,
          shortLabel: `'${s.slice(2, 4)}-${s.slice(5)}`,
        }))}
        value={season}
        onChange={setSeason}
      />

      {/* offense vs defense scatter */}
      <section className="mt-10">
        <h2 className="font-display text-xl font-semibold tracking-tight text-ink sm:text-2xl">
          Drawn vs conceded, {season}
        </h2>
        <p className="mt-1.5 max-w-prose text-sm text-ink-soft">
          Shooting-foul free throws over expected per 100 possessions, both
          ends. Drawn is the offense; conceded is the defense. Top-right both
          draws a lot and gives a lot up.
        </p>
        <div className="mt-6">
          <TeamScatter
            teams={data.teams[season] ?? []}
            off={(t) => t.drawn}
            def={(t) => t.conceded}
            xAxis="draws more →"
            defLabel="Conceded"
          />
        </div>
        <p className="mt-2 max-w-prose text-xs leading-relaxed text-ink-faint">
          Each dot is a team, centered on the league average on both axes. Warm
          dots draw more than they concede, cool dots the reverse.
        </p>
      </section>

      {/* ranked table */}
      <section className="mt-14">
        <h2 className="font-display text-xl font-semibold tracking-tight text-ink sm:text-2xl">
          Who draws, who concedes
        </h2>
        <div className="mt-6 grid grid-cols-[2rem_minmax(0,1fr)_6rem_6.5rem] items-end gap-x-4 border-b border-line pb-2">
          <span />
          <span className="font-display text-[11px] font-medium uppercase tracking-wider text-ink-faint">
            Team
          </span>
          {(["drawn", "conceded"] as const).map((k) => (
            <button
              key={k}
              type="button"
              onClick={() => setSide(k)}
              aria-pressed={side === k}
              className={`text-right font-display text-[11px] font-medium uppercase tracking-wider transition-colors duration-150 ${
                side === k ? "text-ink" : "text-ink-faint hover:text-ink-soft"
              }`}
            >
              {k}
              <span className="ml-1 inline-block w-2 font-mono">
                {side === k ? "↓" : ""}
              </span>
            </button>
          ))}
        </div>
        <ol>
          {teams.map((t: TeamRow, i) => (
            <li
              key={t.team}
              className="grid grid-cols-[2rem_minmax(0,1fr)_6rem_6.5rem] items-center gap-x-4 border-b border-line-soft py-2"
            >
              <span className="text-right font-mono tnum text-xs text-ink-faint">
                {i + 1}
              </span>
              <span className="font-display text-[14px] font-semibold text-ink">
                {t.team}
              </span>
              <span
                className="text-right font-mono tnum text-sm"
                style={{ color: divergingText(t.drawn) }}
              >
                {signed(t.drawn, 1)}
              </span>
              <span
                className="text-right font-mono tnum text-sm"
                style={{ color: divergingText(t.conceded) }}
              >
                {signed(t.conceded, 1)}
              </span>
            </li>
          ))}
        </ol>
        <p className="mt-3 text-xs leading-relaxed text-ink-faint">
          Warm = more shooting-foul free throws than expected, cool = fewer; for
          conceded, warm means the defense gives them up. A player's number
          partly rides on this: check his team before crediting him alone.
        </p>
      </section>

      {/* the foul environment over time + the crackdown */}
      <section className="mt-16 border-t border-line pt-12">
        <h2 className="font-display text-xl font-semibold tracking-tight text-ink sm:text-2xl">
          The foul environment, over time
        </h2>
        <p className="mt-1.5 max-w-prose text-sm leading-relaxed text-ink-soft">
          League-wide shooting-foul free throws per 100 possessions, season by
          season. The 2021-22 crackdown on non-basketball moves barely dented
          the league rate: it repriced a handful of players rather than changing
          the whole game, and the environment drifted back up the next season.
        </p>
        <div className="mt-6 max-w-2xl">
          <LeagueTrend seasons={seasons} rates={data.meta.leagueRateBySeason} />
        </div>
        <p className="mt-4 text-sm text-ink-soft">
          <Link
            to="/crackdown"
            className="font-display font-medium text-ink underline underline-offset-4 transition-colors duration-150 hover:text-ink-soft focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
          >
            The 2021-22 crackdown, measured →
          </Link>
        </p>
      </section>
    </div>
  );
}
