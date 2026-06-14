import { useMemo } from "react";
import type { CSSProperties } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { useData } from "../data";
import { useTitle } from "../lib/useTitle";
import { int, signed } from "../lib/format";
import SegmentedControl from "../components/SegmentedControl";

const SCRIPT_LABEL: Record<string, { label: string; sub: string }> = {
  close: { label: "Close", sub: "decided by ≤ 5" },
  mid: { label: "Middling", sub: "6 to 12" },
  blowout: { label: "Blowout", sub: "13 or more" },
};

function NotFound() {
  return (
    <div className="mx-auto max-w-xl px-5 py-28 text-center sm:px-8">
      <p className="font-display text-2xl font-semibold text-ink">
        No profile for this official.
      </p>
      <p className="mt-3 text-sm leading-relaxed text-ink-soft">
        Profiles require at least 20 games in a season.
      </p>
      <Link
        to="/referees"
        className="mt-8 inline-block rounded-md bg-ink px-5 py-2.5 font-display text-sm font-medium text-paper transition-opacity duration-150 hover:opacity-85 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
      >
        All referees
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

/**
 * Each row is one slice (a quarter, or a game script). The center line is the
 * league baseline for that same slice; the bar runs right when the official
 * called more shooting-foul free throws than the league saw in those
 * situations, left when fewer. Neutral on purpose: this is an official's
 * tendency, not a player's FTAOE, so it never borrows the warm/cool scale.
 */
function WhistleChart({
  rows,
}: {
  rows: { label: string; sub: string; per100: number; lg: number }[];
}) {
  const scale = Math.max(1.5, ...rows.map((r) => Math.abs(r.per100 - r.lg))) * 1.15;
  return (
    <div className="mt-5">
      {rows.map((r) => {
        const diff = r.per100 - r.lg;
        const t = Math.min(Math.abs(diff), scale) / scale;
        const fill: CSSProperties = {
          width: `${(t * 50).toFixed(2)}%`,
          background: "var(--color-ink-soft)",
        };
        if (diff >= 0) fill.left = "50%";
        else fill.right = "50%";
        return (
          <div
            key={r.label}
            className="grid grid-cols-[4.75rem_minmax(0,1fr)_5rem] items-center gap-3 border-b border-line-soft py-3 last:border-b-0 sm:grid-cols-[6rem_minmax(0,1fr)_6rem]"
          >
            <span className="min-w-0">
              <span className="block font-display text-sm font-semibold text-ink">
                {r.label}
              </span>
              <span className="block truncate text-[11px] text-ink-faint">
                {r.sub}
              </span>
            </span>
            <span className="relative block h-2" aria-hidden="true">
              <span className="absolute inset-y-0 left-1/2 w-px bg-line" />
              <span className="absolute top-0 h-full rounded-full" style={fill} />
            </span>
            <span className="text-right">
              <span className="block font-mono tnum text-sm text-ink">
                {r.per100.toFixed(1)}
              </span>
              <span className="block font-mono tnum text-[11px] text-ink-faint">
                {signed(diff, 1)} vs {r.lg.toFixed(1)}
              </span>
            </span>
          </div>
        );
      })}
    </div>
  );
}

export default function Referee() {
  const data = useData();
  const { id } = useParams();
  const [params, setParams] = useSearchParams();

  const prof = id ? data.refProfiles[id] : undefined;

  // Career pooling across this official's qualified seasons.
  const career = useMemo(() => {
    if (!prof) return null;
    let games = 0,
      poss = 0,
      fta = 0;
    for (const d of Object.values(prof.detail)) {
      games += d.games;
      poss += d.poss;
      fta += d.fta;
    }
    return { games, poss, per100: poss ? (fta / poss) * 100 : 0 };
  }, [prof]);

  const seasons = prof?.seasons ?? [];
  const requested = params.get("season");
  const season =
    requested && seasons.includes(requested)
      ? requested
      : seasons[seasons.length - 1] ?? null;
  const detail = prof && season ? prof.detail[season] : undefined;

  useTitle(prof ? `${prof.name} · FTAOE` : "FTAOE");

  if (!prof || !season || !detail) return <NotFound />;

  const setSeason = (s: string) => {
    const next = new URLSearchParams(params);
    next.set("season", s);
    setParams(next);
  };

  const quarterRows = detail.quarters
    .filter((q) => q.q !== "OT")
    .map((q) => ({
      label: q.q,
      sub: `${int(q.poss)} poss`,
      per100: q.per100,
      lg: q.lg,
    }));
  const scriptRows = detail.script.map((s) => ({
    label: SCRIPT_LABEL[s.b]?.label ?? s.b,
    sub: `${int(s.games)} games · ${SCRIPT_LABEL[s.b]?.sub ?? ""}`,
    per100: s.per100,
    lg: s.lg,
  }));

  const diff = detail.per100 - detail.lg;
  const careerDiff = career ? career.per100 - data.meta.leagueRatePer100 : 0;

  return (
    <div className="mx-auto max-w-4xl px-5 py-10 sm:px-8 sm:py-14">
      <Link
        to={`/referees?season=${encodeURIComponent(season)}`}
        className="font-display text-sm text-ink-soft transition-colors duration-150 hover:text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
      >
        ← Referees
      </Link>

      <header className="mt-6">
        <p className="font-display text-[11px] font-medium uppercase tracking-wider text-ink-faint">
          Official
        </p>
        <h1 className="mt-1 font-display text-4xl font-bold tracking-tight text-ink sm:text-6xl">
          {prof.name}
        </h1>
        <p className="mt-3 text-sm text-ink-soft">
          {int(detail.games)} games in {season}
          {career && career.games > detail.games
            ? ` · ${int(career.games)} across ${int(seasons.length)} seasons`
            : ""}
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
        <Stat delay={0} value={int(detail.games)} label="Games worked" />
        <Stat
          delay={60}
          value={int(detail.poss)}
          label="Possessions"
          sub="officiated"
        />
        <Stat
          delay={120}
          value={detail.per100.toFixed(1)}
          label="FTA per 100 poss"
          sub={`league: ${detail.lg.toFixed(1)}`}
        />
        <Stat
          delay={180}
          value={signed(diff, 1)}
          label="vs league rate"
          sub="their games"
        />
      </section>

      <p className="mt-6 max-w-prose text-sm leading-relaxed text-ink-soft">
        Across the games {prof.name.split(" ").slice(-1)[0]} worked in {season},
        shooting fouls sent players to the line{" "}
        <span className="font-mono tnum">{detail.per100.toFixed(1)}</span> times
        per 100 possessions, against a league rate of{" "}
        <span className="font-mono tnum">{detail.lg.toFixed(1)}</span> — a{" "}
        <span className="font-mono tnum">{signed(diff, 1)}</span> gap.
      </p>

      {/* by quarter */}
      <section className="mt-14">
        <h2 className="font-display text-xl font-semibold tracking-tight text-ink sm:text-2xl">
          How the whistle moves by quarter
        </h2>
        <p className="mt-1.5 max-w-prose text-sm text-ink-soft">
          Shooting-foul free throws per 100 possessions, by quarter, each
          measured against the league's own rate for that quarter. Fouls climb
          league-wide as games tighten and the bonus arrives; this shows where
          this official sits within that.
        </p>
        <WhistleChart rows={quarterRows} />
      </section>

      {/* by game script */}
      <section className="mt-14">
        <h2 className="font-display text-xl font-semibold tracking-tight text-ink sm:text-2xl">
          Close games vs blowouts
        </h2>
        <p className="mt-1.5 max-w-prose text-sm text-ink-soft">
          The same rate split by how the game finished, each against the
          league's rate for games of that kind. Whether a whistle tightens or
          loosens once a game is out of reach shows up here.
        </p>
        <WhistleChart rows={scriptRows} />
      </section>

      {/* career */}
      {career && seasons.length > 1 && (
        <section className="mt-14">
          <h2 className="font-display text-xl font-semibold tracking-tight text-ink sm:text-2xl">
            Across seasons
          </h2>
          <p className="mt-1.5 max-w-prose text-sm text-ink-soft">
            {int(career.games)} games over {int(seasons.length)} seasons:{" "}
            <span className="font-mono tnum">{career.per100.toFixed(1)}</span>{" "}
            shooting-foul free throws per 100 possessions, a{" "}
            <span className="font-mono tnum">{signed(careerDiff, 1)}</span> gap
            from the all-seasons league rate of{" "}
            <span className="font-mono tnum">
              {data.meta.leagueRatePer100.toFixed(1)}
            </span>
            .
          </p>
        </section>
      )}

      <p className="mt-14 border-t border-line pt-6 max-w-prose text-xs leading-relaxed text-ink-faint">
        Descriptive, league-level only. Crew tendency is one of the context
        features the expected-FTA model already adjusts for, and assignments
        are not random — workloads, slates and the games an official is given
        all differ. This site deliberately does not publish player-by-official
        splits.{" "}
        <Link
          to="/methodology"
          className="underline underline-offset-2 transition-colors duration-150 hover:text-ink"
        >
          Methodology
        </Link>
        .
      </p>

      <p className="mt-8">
        <Link
          to={`/referees?season=${encodeURIComponent(season)}`}
          className="font-display text-sm font-medium text-ink underline underline-offset-4 transition-colors duration-150 hover:text-ink-soft focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
        >
          See every official →
        </Link>
      </p>
    </div>
  );
}
