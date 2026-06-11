import { useMemo } from "react";
import { flushSync } from "react-dom";
import type { CSSProperties } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useData } from "../data";
import type { LeaderboardRow } from "../types";
import { divergingColor, SCALE_MAX } from "../lib/color";
import { int, ordinal } from "../lib/format";
import { Delta } from "../components/Delta";
import { useTitle } from "../lib/useTitle";
import SegmentedControl from "../components/SegmentedControl";

type SortKey = "per100" | "poss" | "pct";

const POSITIONS = ["All", "Guard", "Forward", "Center"];
const SORT_LABEL: Record<SortKey, string> = {
  per100: "FTAOE/100",
  poss: "Poss",
  pct: "Percentile",
};

/** Centered-axis diverging bar; identical geometry every row. */
function DivergingBar({
  per100,
  className = "w-24",
}: {
  per100: number;
  className?: string;
}) {
  const t = Math.min(Math.abs(per100), SCALE_MAX) / SCALE_MAX;
  const fill: CSSProperties = {
    background: divergingColor(per100),
    width: `${(t * 50).toFixed(2)}%`,
  };
  if (per100 >= 0) fill.left = "50%";
  else fill.right = "50%";
  return (
    <span className={`relative block h-1.5 ${className}`} aria-hidden="true">
      <span className="absolute inset-y-0 left-1/2 w-px bg-line" />
      <span className="absolute top-0 h-full rounded-full" style={fill} />
    </span>
  );
}

function PctCell({ pct }: { pct: number | null }) {
  if (pct === null) {
    return <span className="font-mono text-sm text-ink-faint">—</span>;
  }
  return (
    <span className="block">
      <span className="font-mono tnum text-sm text-ink">
        {ordinal(Math.floor(pct))} <span className="text-ink-faint">%ile</span>
      </span>
      <span className="mt-1 block h-1 w-16 bg-wash" aria-hidden="true">
        <span
          className="block h-full bg-ink-faint"
          style={{ width: `${pct.toFixed(1)}%` }}
        />
      </span>
    </span>
  );
}

function SortHeader({
  k,
  sort,
  dir,
  onSort,
  className = "",
}: {
  k: SortKey;
  sort: SortKey;
  dir: "asc" | "desc";
  onSort: (k: SortKey) => void;
  className?: string;
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
      {SORT_LABEL[k]}
      <span className="ml-1 inline-block w-2 font-mono">
        {active ? (dir === "desc" ? "↓" : "↑") : ""}
      </span>
    </button>
  );
}

export default function Leaderboard() {
  const data = useData();
  const [params, setParams] = useSearchParams();
  useTitle("Leaderboard \u00b7 FTAOE");

  const seasons = data.meta.seasons;
  const latest = seasons[seasons.length - 1];
  const qualify = data.meta.qualifyPossessions;

  const season = seasons.includes(params.get("season") ?? "")
    ? (params.get("season") as string)
    : latest;
  const sort = (["per100", "poss", "pct"].includes(params.get("sort") ?? "")
    ? params.get("sort")
    : "per100") as SortKey;
  const dir = params.get("dir") === "asc" ? "asc" : "desc";
  const pos = POSITIONS.includes(params.get("pos") ?? "")
    ? (params.get("pos") as string)
    : "All";
  const minPoss = Math.max(
    0,
    Math.min(2000, Number(params.get("min") ?? qualify) || 0),
  );

  const update = (patch: Record<string, string>) => {
    const apply = () => {
      const next = new URLSearchParams(params);
      for (const [k, v] of Object.entries(patch)) next.set(k, v);
      setParams(next, { replace: false });
    };
    // Animated reorder via the View Transitions API where available;
    // plain update under reduced motion or older browsers.
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (!reduce && "startViewTransition" in document) {
      document.startViewTransition(() => flushSync(apply));
    } else {
      apply();
    }
  };
  const onSort = (k: SortKey) =>
    update(
      k === sort
        ? { dir: dir === "desc" ? "asc" : "desc" }
        : { sort: k, dir: "desc" },
    );

  const rows = useMemo(() => {
    const mul = dir === "asc" ? 1 : -1;
    const cmp = (a: LeaderboardRow, b: LeaderboardRow): number => {
      if (sort === "pct") {
        if (a.pct === null && b.pct === null) return mul * (a.per100 - b.per100);
        if (a.pct === null) return 1; // nulls always last
        if (b.pct === null) return -1;
        return mul * (a.pct - b.pct);
      }
      return mul * (a[sort] - b[sort]);
    };
    return data.leaderboard
      .filter(
        (r) =>
          r.season === season &&
          r.poss >= minPoss &&
          (pos === "All" || r.pos === pos),
      )
      .sort(cmp);
  }, [data.leaderboard, season, minPoss, pos, sort, dir]);

  return (
    <div>
      {/* controls */}
      <div className="sticky top-0 z-10 border-b border-line bg-paper/95 backdrop-blur">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-5 gap-y-3 px-5 py-3 sm:px-8">
          <SegmentedControl
            ariaLabel="Season"
            options={seasons.map((s) => ({
              value: s,
              label: s,
              shortLabel: `'${s.slice(2, 4)}-${s.slice(5)}`,
            }))}
            value={season}
            onChange={(s) => update({ season: s })}
          />
          <SegmentedControl
            ariaLabel="Position"
            options={POSITIONS.map((p) => ({
              value: p,
              label: p === "All" ? "All" : p.slice(0, 1),
            }))}
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
        {/* mobile sort */}
        <div className="mx-auto flex max-w-6xl items-center gap-4 px-5 pb-3 sm:hidden">
          {(["per100", "poss", "pct"] as SortKey[]).map((k) => (
            <SortHeader key={k} k={k} sort={sort} dir={dir} onSort={onSort} />
          ))}
        </div>
      </div>

      <div className="mx-auto max-w-6xl px-5 pb-8 pt-8 sm:px-8 sm:pt-12">
        <h1 className="font-display text-3xl font-bold tracking-tight sm:text-4xl">
          Leaderboard
        </h1>
        <p className="mt-2 max-w-2xl text-sm leading-relaxed text-ink-soft">
          Free throw attempts over expected per 100 possessions, {season}.
          Expected = the league-average shooting-foul rate over the same
          number of possessions.
        </p>

        {/* desktop header row */}
        <div className="mt-8 hidden grid-cols-[2.75rem_minmax(0,1fr)_7.5rem_6.5rem_11.5rem] items-end gap-x-4 border-b border-line pb-2 sm:grid">
          <span />
          <span className="font-display text-[11px] font-medium uppercase tracking-wider text-ink-faint">
            Player
          </span>
          <span className="text-right font-display text-[11px] font-medium uppercase tracking-wider text-ink-faint">
            FTA vs exp.
          </span>
          <SortHeader k="pct" sort={sort} dir={dir} onSort={onSort} className="text-left" />
          <span className="flex items-center justify-end gap-4 whitespace-nowrap">
            <SortHeader k="poss" sort={sort} dir={dir} onSort={onSort} />
            <SortHeader k="per100" sort={sort} dir={dir} onSort={onSort} />
          </span>
        </div>

        {rows.length === 0 ? (
          <p className="py-16 text-center text-sm text-ink-faint">
            No players match — lower the possession floor.
          </p>
        ) : (
          <ol>
            {rows.map((r, i) => (
              <li
                key={`${r.id}-${r.season}`}
                style={
                  i < 40
                    ? ({ viewTransitionName: `lb-${r.id}` } as React.CSSProperties)
                    : undefined
                }
              >
                <Link
                  to={`/player/${r.id}?season=${encodeURIComponent(r.season)}`}
                  className="group block border-b border-line-soft transition-colors duration-150 hover:bg-wash focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-ink"
                >
                  {/* desktop row */}
                  <div className="hidden grid-cols-[2.75rem_minmax(0,1fr)_7.5rem_6.5rem_11.5rem] items-center gap-x-4 py-3 sm:grid">
                    <span className="text-right font-mono tnum text-sm text-ink-faint">
                      {i + 1}
                    </span>
                    <span className="min-w-0">
                      <span className="block truncate font-display text-[15px] font-semibold text-ink">
                        {r.name}
                      </span>
                      <span className="block truncate text-xs text-ink-soft">
                        {r.teams.join(" · ")}
                        {r.pos ? ` · ${r.pos}` : ""} · {int(r.poss)} poss
                      </span>
                    </span>
                    <span className="text-right font-mono tnum text-sm text-ink-soft">
                      {int(r.fta)}{" "}
                      <span className="text-ink-faint">vs {r.xfta.toFixed(1)}</span>
                    </span>
                    <PctCell pct={r.pct} />
                    <span className="flex items-center justify-end gap-3">
                      <DivergingBar per100={r.per100} />
                      <Delta per100={r.per100} className="w-14 text-right text-lg" />
                    </span>
                  </div>
                  {/* mobile row */}
                  <div className="flex flex-col gap-1.5 py-3 sm:hidden">
                    <span className="flex items-baseline gap-2.5">
                      <span className="w-7 text-right font-mono tnum text-xs text-ink-faint">
                        {i + 1}
                      </span>
                      <span className="min-w-0 flex-1 truncate font-display text-[15px] font-semibold text-ink">
                        {r.name}
                      </span>
                      <Delta per100={r.per100} className="text-lg" />
                    </span>
                    <span className="flex items-center gap-2.5 pl-9">
                      <span className="min-w-0 flex-1 truncate text-xs text-ink-soft">
                        {r.teams.join(" · ")}
                        {r.pos ? ` · ${r.pos.slice(0, 1)}` : ""} · {int(r.poss)} poss
                        {r.pct !== null ? ` · ${ordinal(Math.floor(r.pct))} %ile` : ""}
                      </span>
                      <DivergingBar per100={r.per100} className="w-16" />
                    </span>
                  </div>
                </Link>
              </li>
            ))}
          </ol>
        )}

        {minPoss < qualify && (
          <p className="mt-4 text-xs leading-relaxed text-ink-faint">
            Percentiles are computed within the qualified pool (≥ {int(qualify)}{" "}
            possessions); players below the threshold show — instead of an
            unstable percentile.
          </p>
        )}
      </div>
    </div>
  );
}
