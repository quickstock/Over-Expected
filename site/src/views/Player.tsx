import { useMemo, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { useData, usePlayerChunk } from "../data";
import type { GameLine, LeaderboardRow, ShotValueRow } from "../types";
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

type Lens = "value" | "making" | "fouls";

/** Percentile of `v` within `pool` (share at or below), or null if empty. */
function pctOf(pool: number[], v: number): number | null {
  if (pool.length === 0) return null;
  return (pool.filter((x) => x <= v).length / pool.length) * 100;
}

/**
 * Shot value / shot-making lens for a player-season: the headline stat band
 * plus where he ranks within the season's qualified shot-value pool. The
 * foul-drawing lens keeps the deep per-game sections; these two reframe the
 * top line around points and conversion.
 */
function ShotQualityPanel({ lens, season, sv, pool }: {
  lens: "value" | "making";
  season: string;
  sv: ShotValueRow;
  pool: ShotValueRow[];
}) {
  const poePool = pool.map((r) => r.poe100);
  const fgPool = pool.map((r) => r.fgPoe100);
  const ftPool = pool.map((r) => r.ftaoe100);
  const makePool = pool.map((r) => r.makeOE);

  return (
    <>
      {/* stat band */}
      <section className="mt-10 grid grid-cols-2 divide-line border-y border-line py-2 max-sm:[&>*:nth-child(odd)]:border-r max-sm:[&>*:nth-child(-n+2)]:border-b sm:grid-cols-4 sm:divide-x sm:py-5">
        {lens === "value" ? (
          <>
            <Stat
              delay={0}
              value={
                <span className="text-4xl sm:text-5xl" style={{ color: divergingText(sv.poe100) }}>
                  {signed(sv.poe100, 1)}
                </span>
              }
              label="Points over expected / 100"
            />
            <Stat
              delay={60}
              value={<span style={{ color: divergingText(sv.makeOE) }}>{signed(sv.makeOE, 1)}</span>}
              label="Shot-making"
              sub="FG% − xFG%, pp"
            />
            <Stat delay={120} value={sv.xptsShot.toFixed(2)} label="Expected points/shot" sub="value of the looks he takes" />
            <Stat
              delay={180}
              value={<span style={{ color: divergingText(sv.ftaoe100) }}>{signed(sv.ftaoe100, 1)}</span>}
              label="Foul-drawing / 100"
            />
          </>
        ) : (
          <>
            <Stat
              delay={0}
              value={
                <span className="text-4xl sm:text-5xl" style={{ color: divergingText(sv.fgPoe100) }}>
                  {signed(sv.fgPoe100, 1)}
                </span>
              }
              label="FG points over expected / 100"
            />
            <Stat
              delay={60}
              value={<span style={{ color: divergingText(sv.makeOE) }}>{signed(sv.makeOE, 1)}</span>}
              label="Make over expected"
              sub="FG% − xFG%, pp"
            />
            <Stat delay={120} value={`${sv.fgPct.toFixed(1)}`} label="Field-goal %" />
            <Stat delay={180} value={`${sv.xfgPct.toFixed(1)}`} label="Expected FG%" sub="from the looks he took" />
          </>
        )}
      </section>

      {/* where he ranks */}
      <section className="mt-6 border-b border-line-soft pb-4">
        <h2 className="font-display text-[11px] font-medium uppercase tracking-wider text-ink-faint">
          Where he ranks
        </h2>
        <PercentileSliders
          className="mt-1"
          rows={
            lens === "value"
              ? [
                  { label: `Points OE/100, ${season}`, per100: sv.poe100, pct: pctOf(poePool, sv.poe100) },
                  { label: "FG pts OE/100", per100: sv.fgPoe100, pct: pctOf(fgPool, sv.fgPoe100) },
                  { label: "FTAOE/100", per100: sv.ftaoe100, pct: pctOf(ftPool, sv.ftaoe100) },
                ]
              : [
                  { label: `FG points OE/100, ${season}`, per100: sv.fgPoe100, pct: pctOf(fgPool, sv.fgPoe100) },
                  { label: "Make over expected", per100: sv.makeOE, pct: pctOf(makePool, sv.makeOE) },
                ]
          }
        />
      </section>

      <p className="mt-6 max-w-2xl text-xs leading-relaxed text-ink-faint">
        {lens === "value" ? (
          <>
            Expected points fuse the leak-free xFG% model (shot difficulty) with
            the FTAOE model (fouls drawn vs expected); free throws are valued at
            his own FT%. Ranks are within the {int(pool.length)} qualified
            players in {season}.{" "}
          </>
        ) : (
          <>
            xFG% is the shooter-agnostic expectation of the looks he took, leak-free
            by season. Field goals only here; see Shot value for the full picture.
            Ranks are within the {int(pool.length)} qualified players in {season}.{" "}
          </>
        )}
        <Link to="/methodology" className="underline underline-offset-2 transition-colors duration-150 hover:text-ink">
          Methodology
        </Link>
        .
      </p>
    </>
  );
}

const LENS_OPTS: { value: Lens; label: string }[] = [
  { value: "value", label: "Shot value" },
  { value: "making", label: "Shot-making" },
  { value: "fouls", label: "Foul-drawing" },
];

export default function Player() {
  const data = useData();
  const { id } = useParams();
  const [params, setParams] = useSearchParams();
  const [formWindow, setFormWindow] = useState("10");
  const [courtMode, setCourtMode] = useState("attempts");
  const lens = (LENS_OPTS.some((o) => o.value === params.get("lens"))
    ? params.get("lens")
    : "fouls") as Lens;

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
  useTitle(row ? `${row.name} · Over Expected` : "Over Expected");
  const animatedPer100 = useCountUp(row?.per100 ?? 0);

  if (!row || !season) return <NotFound qualify={qualify} />;

  const detail =
    chunk.status === "ready" ? chunk.chunk[String(row.id)] : undefined;
  const fouls = detail?.fouls;

  // Shot-value lens data: this player's row and the season's qualified pool.
  const svPool = data.shotValue?.[season] ?? [];
  const sv = svPool.find((r) => r.id === Number(id));

  // Per-game series reframed for the active lens. Foul-drawing keeps the FTA
  // line; shot-making swaps in FG points; shot value adds the drawn-FT points
  // (banked at his own FT%, expected at the league 0.77).
  const LEAGUE_FT = 0.77;
  const lensGames = useMemo<GameLine[]>(() => {
    const gs = detail?.games ?? [];
    if (lens === "making") return gs.map((g) => [g[3] ?? 0, g[4] ?? 0, g[2]]);
    if (lens === "value") {
      const ft = sv?.ftPct ?? LEAGUE_FT;
      return gs.map((g) => [
        (g[3] ?? 0) + g[0] * ft,
        (g[4] ?? 0) + g[1] * LEAGUE_FT,
        g[2],
      ]);
    }
    return gs;
  }, [detail, lens, sv]);

  // Career trajectory for the active lens, built from the shipped per-season
  // shot-value rows (cast to the CareerStrip row shape it reads: season+per100).
  const svCareer = useMemo<LeaderboardRow[]>(() => {
    const pid = Number(id);
    return data.meta.seasons
      .map((s) => {
        const r = data.shotValue?.[s]?.find((x) => x.id === pid);
        if (!r) return null;
        return {
          season: s,
          per100: lens === "value" ? r.poe100 : r.fgPoe100,
        } as LeaderboardRow;
      })
      .filter((r): r is LeaderboardRow => r !== null);
  }, [data, id, lens]);

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
        <div className="mt-6">
          <SegmentedControl
            ariaLabel="Metric"
            options={LENS_OPTS}
            value={lens}
            onChange={(l) => {
              const next = new URLSearchParams(params);
              next.set("lens", l);
              setParams(next);
            }}
          />
        </div>
      </header>

      {lens === "fouls" && (
        <>
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
              "–"
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

      {/* style-adjusted: a secondary read, kept below the headline number */}
      {row.sper100 !== null && row.spct !== null && (
        <section className="mt-14">
          <h2 className="font-display text-xl font-semibold tracking-tight text-ink sm:text-2xl">
            Style-adjusted
          </h2>
          <p className="mt-1.5 max-w-prose text-sm text-ink-soft">
            A different question than the headline: how much he draws above what
            his attack profile (drives, paint and post touches) predicts.{" "}
            <Link
              to="/methodology"
              className="underline underline-offset-2 transition-colors duration-150 hover:text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
            >
              How it differs
            </Link>
            .
          </p>
          <PercentileSliders
            className="mt-3 max-w-2xl"
            rows={[
              {
                label: `Style-adjusted/100, ${season}`,
                per100: row.sper100,
                pct: row.spct,
              },
            ]}
          />
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
        </>
      )}

      {lens !== "fouls" &&
        (sv ? (
          <>
            <ShotQualityPanel lens={lens} season={season} sv={sv} pool={svPool} />

            {/* the gap, in points */}
            <section className="mt-14">
              <h2 className="font-display text-xl font-semibold tracking-tight text-ink sm:text-2xl">
                The season, drawn as a gap
              </h2>
              <p className="mt-1.5 text-sm text-ink-soft">
                {lens === "value"
                  ? "Cumulative points generated vs what an average shot diet would yield, game by game: field goals plus the free throws drawn."
                  : "Cumulative field-goal points vs what his looks were worth, game by game."}
              </p>
              {detail ? (
                <GapArc games={lensGames} className="mt-6" />
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
                    Trailing {formWindow}-game{" "}
                    {lens === "value" ? "points" : "FG points"} over expected per
                    100 possessions, through the season.
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
                <FormStrip games={lensGames} window={Number(formWindow)} className="mt-6" />
              ) : chunk.status === "error" ? null : (
                <div className="mt-6 h-[200px] animate-pulse rounded bg-wash" aria-busy="true" />
              )}
            </section>

            {/* where it happens */}
            <section className="mt-14">
              <h2 className="font-display text-xl font-semibold tracking-tight text-ink sm:text-2xl">
                Where it happens
              </h2>
              <p className="mt-1.5 text-sm text-ink-soft">
                Charged field-goal attempts by zone, {season}.
              </p>
              {detail ? (
                <CourtZones zones={detail.zones} className="mt-6 max-w-[520px]" />
              ) : chunk.status === "error" ? null : (
                <div className="mt-6 aspect-[500/434] max-w-[520px] animate-pulse rounded bg-wash" aria-busy="true" />
              )}
            </section>

            {/* free-throw ledger, relevant to shot value (FTs count), not making */}
            {lens === "value" && fouls && (
              <section className="mt-14">
                <h2 className="font-display text-xl font-semibold tracking-tight text-ink sm:text-2xl">
                  Every free throw, accounted for
                </h2>
                <p className="mt-1.5 text-sm text-ink-soft">
                  The free throws folded into his points: and-1s award one, fouled
                  2-pt misses two, fouled 3-pt misses three.
                </p>
                <FoulLedger fouls={fouls} fta={row.fta} className="mt-6" />
              </section>
            )}

            {/* career */}
            {svCareer.length > 1 && (
              <section className="mt-14">
                <h2 className="font-display text-xl font-semibold tracking-tight text-ink sm:text-2xl">
                  Career
                </h2>
                <p className="mt-1.5 text-sm text-ink-soft">
                  {lens === "value" ? "Points" : "FG points"} over expected per 100
                  possessions by season. Tap a season.
                </p>
                <CareerStrip
                  rows={svCareer}
                  activeSeason={season}
                  onSelect={setSeason}
                  className="mt-4 max-w-2xl"
                />
              </section>
            )}
          </>
        ) : (
          <p className="mt-10 rounded border border-line-soft bg-wash px-4 py-10 text-center text-sm text-ink-faint">
            No shot-value data for {row.name} in {season}. Player pages require at
            least {int(qualify)} possessions.
          </p>
        ))}

      <p className="mt-16 border-t border-line pt-6">
        <Link
          to={`/leaderboard?season=${encodeURIComponent(season)}`}
          className="font-display text-sm font-medium text-ink underline underline-offset-4 transition-colors duration-150 hover:text-ink-soft focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
        >
          See everyone →
        </Link>
        <Link
          to={`/compare?a=${row.id}&season=${encodeURIComponent(season)}`}
          className="ml-6 font-display text-sm font-medium text-ink underline underline-offset-4 transition-colors duration-150 hover:text-ink-soft focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
        >
          Compare him →
        </Link>
      </p>
    </div>
  );
}
