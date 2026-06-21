import { useMemo, useTransition } from "react";
import type { CSSProperties, ReactNode } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useData } from "../../data";
import type { ShotValueRow } from "../../types";
import { divergingColor } from "../../lib/color";
import { int, signed } from "../../lib/format";
import { Delta } from "../../components/Delta";
import SegmentedControl from "../../components/SegmentedControl";

type Mode = "value" | "making";
type SortKey = "poe100" | "makeOE" | "xptsShot" | "ftaoe100" | "fgPoe100";

const SORT_LABEL: Record<SortKey, string> = {
  poe100: "Pts over exp.",
  makeOE: "Make OE",
  xptsShot: "Exp. pts/shot",
  ftaoe100: "Foul-drawing",
  fgPoe100: "FG pts over exp.",
};

// Sortable columns and the default headline sort, per lens.
const SORTS: Record<Mode, SortKey[]> = {
  value: ["makeOE", "xptsShot", "ftaoe100", "poe100"],
  making: ["makeOE", "fgPoe100"],
};
const HEADLINE: Record<Mode, SortKey> = { value: "poe100", making: "fgPoe100" };
const POSITIONS = ["All", "Guard", "Forward", "Center"];

/** Diverging bar centred on zero; scale set per metric so bars stay legible. */
function DivBar({ value, scale, className = "w-20" }: {
  value: number; scale: number; className?: string;
}) {
  const t = Math.min(Math.abs(value), scale) / scale;
  const fill: CSSProperties = {
    background: divergingColor(value),
    width: `${(t * 50).toFixed(2)}%`,
  };
  if (value >= 0) fill.left = "50%";
  else fill.right = "50%";
  return (
    <span className={`relative block h-1.5 ${className}`} aria-hidden="true">
      <span className="absolute inset-y-0 left-1/2 w-px bg-line" />
      <span className="absolute top-0 h-full rounded-full" style={fill} />
    </span>
  );
}

/** Neutral bar for the absolute shot-quality value (not an over/under stat). */
function QualBar({ value, lo = 0.85, hi = 1.65 }: { value: number; lo?: number; hi?: number }) {
  const t = Math.max(0, Math.min(1, (value - lo) / (hi - lo)));
  return (
    <span className="relative block h-1.5 w-16 bg-wash" aria-hidden="true">
      <span className="block h-full rounded-full bg-ink-faint"
        style={{ width: `${(t * 100).toFixed(1)}%` }} />
    </span>
  );
}

function SortHeader({ k, label, sort, dir, onSort, className = "" }: {
  k: SortKey; label?: string; sort: SortKey; dir: "asc" | "desc";
  onSort: (k: SortKey) => void; className?: string;
}) {
  const active = sort === k;
  return (
    <button
      type="button"
      onClick={() => onSort(k)}
      aria-pressed={active}
      className={`font-display text-[11px] font-medium uppercase tracking-wider transition-colors duration-150 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink ${
        active ? "text-ink" : "text-ink-faint hover:text-ink-soft"
      } ${className}`}
    >
      {label ?? SORT_LABEL[k]}
      <span className="ml-1 inline-block w-2 font-mono">
        {active ? (dir === "desc" ? "↓" : "↑") : ""}
      </span>
    </button>
  );
}

export default function ShotValueBoard({ lens, lensControl }: {
  lens: Mode; lensControl: ReactNode;
}) {
  const data = useData();
  const [params, setParams] = useSearchParams();
  const [, startTransition] = useTransition();

  const seasons = data.meta.seasons;
  const byseason = data.shotValue ?? {};
  const validSorts = SORTS[lens];
  // Default to the latest season that actually has shot-value rows.
  const withData = seasons.filter((s) => (byseason[s]?.length ?? 0) > 0);
  const latest = withData.includes(data.meta.defaultSeason)
    ? data.meta.defaultSeason
    : withData[withData.length - 1] ?? data.meta.defaultSeason;

  const season = seasons.includes(params.get("season") ?? "")
    ? (params.get("season") as string)
    : latest;
  const sort = (validSorts.includes((params.get("sort") ?? "") as SortKey)
    ? params.get("sort")
    : HEADLINE[lens]) as SortKey;
  const dir = params.get("dir") === "asc" ? "asc" : "desc";
  const pos = POSITIONS.includes(params.get("pos") ?? "")
    ? (params.get("pos") as string)
    : "All";
  const qualify = data.meta.qualifyPossessions;
  const minPoss = Math.max(
    0,
    Math.min(2000, Number(params.get("min") ?? qualify) || 0),
  );

  // Non-urgent: keep the click responsive, run the list re-render off the
  // critical path so rapid lens/season/floor changes stay smooth.
  const update = (patch: Record<string, string>) => {
    startTransition(() => {
      const next = new URLSearchParams(params);
      for (const [k, v] of Object.entries(patch)) next.set(k, v);
      setParams(next, { replace: false });
    });
  };
  const onSort = (k: SortKey) =>
    update(k === sort ? { dir: dir === "desc" ? "asc" : "desc" } : { sort: k, dir: "desc" });

  const rows = useMemo(() => {
    const mul = dir === "asc" ? 1 : -1;
    return [...(byseason[season] ?? [])]
      .filter((r) => (pos === "All" || r.pos === pos) && r.poss >= minPoss)
      .sort((a, b) => mul * ((a[sort as keyof ShotValueRow] as number) - (b[sort as keyof ShotValueRow] as number)));
  }, [byseason, season, sort, dir, pos, minPoss]);

  const GRID = lens === "value"
    ? "grid-cols-[2.5rem_minmax(0,1fr)_6.5rem_6.5rem_6rem_7.5rem]"
    : "grid-cols-[2.5rem_minmax(0,1fr)_7rem_6rem_8rem]";

  return (
    <div>
      {/* controls */}
      <div className="sticky top-0 z-10 border-b border-line bg-paper/95 backdrop-blur">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-5 gap-y-3 px-5 py-3 sm:px-8">
          {lensControl}
          <SegmentedControl
            ariaLabel="Season"
            options={seasons.map((s) => ({
              value: s, label: s, shortLabel: `'${s.slice(2, 4)}-${s.slice(5)}`,
            }))}
            value={season}
            onChange={(s) => update({ season: s })}
          />
          <SegmentedControl
            ariaLabel="Position"
            options={POSITIONS.map((p) => ({ value: p, label: p === "All" ? "All" : p.slice(0, 1) }))}
            value={pos}
            onChange={(p) => update({ pos: p })}
          />
          <label className="flex items-center gap-2.5">
            <span className="font-display text-[11px] font-medium uppercase tracking-wider text-ink-faint">
              Floor
            </span>
            <input
              type="range"
              min={0}
              max={2000}
              step={50}
              value={minPoss}
              onChange={(e) => update({ min: e.target.value })}
              className="w-28 accent-ink sm:w-40"
              aria-label="Minimum possessions"
            />
            <span className="font-mono tnum w-24 text-xs text-ink-soft">
              ≥ {int(minPoss)} poss
            </span>
          </label>
          <span className="ml-auto font-mono tnum text-xs text-ink-faint">
            {int(rows.length)} players
          </span>
        </div>
        <div className="mx-auto flex max-w-6xl items-center gap-4 px-5 pb-3 sm:hidden">
          {validSorts.map((k) => (
            <SortHeader key={k} k={k} sort={sort} dir={dir} onSort={onSort} />
          ))}
        </div>
      </div>

      <div className="mx-auto max-w-6xl px-5 pb-8 pt-8 sm:px-8 sm:pt-12">
        <h1 className="font-display text-3xl font-bold tracking-tight sm:text-4xl">
          {lens === "value" ? "Shot value" : "Shot-making"}
        </h1>
        {lens === "value" ? (
          <p className="mt-2 max-w-2xl text-sm leading-relaxed text-ink-soft">
            How many points is a shot worth, counting both making it and the
            fouls it draws.{" "}
            <span className="font-mono text-[13px]">
              xPoints = xFG% × points + xFTA × 0.77
            </span>
            . Shot-making over expected, expected points per shot (how good are
            the looks), and the foul-drawing and conversion fused into points
            over expected per 100 possessions, {season}.
          </p>
        ) : (
          <p className="mt-2 max-w-2xl text-sm leading-relaxed text-ink-soft">
            Did he convert better than the look? Actual FG% against the
            calibrated, shooter-agnostic xFG% of the shots he took, expressed as
            field-goal points over expected per 100 possessions, {season}.
            Foul-drawing is set aside here; see Shot value for the full picture.
          </p>
        )}

        {/* desktop header */}
        <div className={`mt-8 hidden ${GRID} items-end gap-x-4 border-b border-line pb-2 sm:grid`}>
          <span />
          <span className="font-display text-[11px] font-medium uppercase tracking-wider text-ink-faint">
            Player
          </span>
          {lens === "value" ? (
            <>
              <SortHeader k="makeOE" label="Shot-making" sort={sort} dir={dir} onSort={onSort} className="text-right" />
              <SortHeader k="xptsShot" sort={sort} dir={dir} onSort={onSort} className="text-right" />
              <SortHeader k="ftaoe100" sort={sort} dir={dir} onSort={onSort} className="text-right" />
              <SortHeader k="poe100" sort={sort} dir={dir} onSort={onSort} className="text-right" />
            </>
          ) : (
            <>
              <span className="text-right font-display text-[11px] font-medium uppercase tracking-wider text-ink-faint">
                FG% / xFG%
              </span>
              <SortHeader k="makeOE" label="Make OE" sort={sort} dir={dir} onSort={onSort} className="text-right" />
              <SortHeader k="fgPoe100" sort={sort} dir={dir} onSort={onSort} className="text-right" />
            </>
          )}
        </div>

        {rows.length === 0 ? (
          <p className="py-16 text-center text-sm text-ink-faint">
            No qualified players this season yet.
          </p>
        ) : (
          <ol>
            {rows.map((r: ShotValueRow, i) => (
              <li key={r.id}>
                <Link
                  to={`/player/${r.id}?season=${encodeURIComponent(season)}&lens=${lens}`}
                  className="group block border-b border-line-soft transition-colors duration-150 hover:bg-wash focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-ink"
                >
                  {/* desktop row */}
                  <div className={`hidden ${GRID} items-center gap-x-4 py-3 sm:grid`}>
                    <span className="text-right font-mono tnum text-sm text-ink-faint">{i + 1}</span>
                    <span className="min-w-0">
                      <span className="block truncate font-display text-[15px] font-semibold text-ink">
                        {r.name}
                      </span>
                      <span className="block truncate text-xs text-ink-soft">
                        {r.teams.join(" · ")}{r.pos ? ` · ${r.pos}` : ""} · {int(r.fga)} FGA
                      </span>
                    </span>
                    {lens === "value" ? (
                      <>
                        {/* shot-making */}
                        <span className="text-right">
                          <Delta per100={r.makeOE} className="text-sm" />
                          <span className="mt-0.5 block font-mono tnum text-[11px] text-ink-faint">
                            {r.fgPct.toFixed(1)}/{r.xfgPct.toFixed(1)}
                          </span>
                        </span>
                        {/* shot quality */}
                        <span className="flex flex-col items-end gap-1">
                          <span className="font-mono tnum text-sm text-ink">{r.xptsShot.toFixed(2)}</span>
                          <QualBar value={r.xptsShot} />
                        </span>
                        {/* foul-drawing */}
                        <span className="text-right">
                          <Delta per100={r.ftaoe100} className="text-sm" />
                        </span>
                        {/* combined */}
                        <span className="flex items-center justify-end gap-3">
                          <DivBar value={r.poe100} scale={24} />
                          <Delta per100={r.poe100} decimals={1} className="w-12 text-right text-lg" />
                        </span>
                      </>
                    ) : (
                      <>
                        {/* FG% / xFG% */}
                        <span className="text-right font-mono tnum text-sm text-ink-soft">
                          {r.fgPct.toFixed(1)}
                          <span className="text-ink-faint"> / {r.xfgPct.toFixed(1)}</span>
                        </span>
                        {/* make over expected (pp) */}
                        <span className="text-right">
                          <Delta per100={r.makeOE} className="text-sm" />
                        </span>
                        {/* FG points over expected /100 */}
                        <span className="flex items-center justify-end gap-3">
                          <DivBar value={r.fgPoe100} scale={16} />
                          <Delta per100={r.fgPoe100} decimals={1} className="w-12 text-right text-lg" />
                        </span>
                      </>
                    )}
                  </div>
                  {/* mobile row */}
                  <div className="flex flex-col gap-1.5 py-3 sm:hidden">
                    <span className="flex items-baseline gap-2.5">
                      <span className="w-7 text-right font-mono tnum text-xs text-ink-faint">{i + 1}</span>
                      <span className="min-w-0 flex-1 truncate font-display text-[15px] font-semibold text-ink">
                        {r.name}
                      </span>
                      <Delta per100={lens === "value" ? r.poe100 : r.fgPoe100} className="text-lg" />
                    </span>
                    <span className="flex items-center gap-2.5 pl-9 text-xs text-ink-soft">
                      <span className="min-w-0 flex-1 truncate">
                        {lens === "value" ? (
                          <>
                            make <span className="font-mono tnum">{signed(r.makeOE, 1)}</span> · quality{" "}
                            <span className="font-mono tnum">{r.xptsShot.toFixed(2)}</span> · fouls{" "}
                            <span className="font-mono tnum">{signed(r.ftaoe100, 1)}</span>
                          </>
                        ) : (
                          <>
                            {r.fgPct.toFixed(1)}/{r.xfgPct.toFixed(1)} FG% · make{" "}
                            <span className="font-mono tnum">{signed(r.makeOE, 1)}</span>
                          </>
                        )}
                      </span>
                      <DivBar value={lens === "value" ? r.poe100 : r.fgPoe100}
                        scale={lens === "value" ? 24 : 16} className="w-16" />
                    </span>
                  </div>
                </Link>
              </li>
            ))}
          </ol>
        )}

        <p className="mt-6 max-w-2xl text-xs leading-relaxed text-ink-faint">
          {lens === "value" ? (
            <>
              Expected points per shot pairs the calibrated xFG% model (shot
              difficulty from location, angle, action and game state) with the
              FTAOE model (fouls drawn vs expected). Free throws are valued at
              each player's own FT%, field goals at his actual conversion, so
              the headline credits both shot-making and free-throw skill.{" "}
            </>
          ) : (
            <>
              xFG% is leakage-free: for each season the model trains on the other
              seasons, so a shot's expected make never comes from a model that
              saw it. The gap to actual FG% is conversion skill, scaled to points
              over expected per 100 possessions.{" "}
            </>
          )}
          <Link to="/methodology" className="underline underline-offset-2 transition-colors duration-150 hover:text-ink">
            Methodology
          </Link>
          .
        </p>
      </div>
    </div>
  );
}
