import { useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useData, usePlayerChunk } from "../data";
import type { LeaderboardRow } from "../types";
import { useTitle } from "../lib/useTitle";
import { divergingColor, divergingText } from "../lib/color";
import { int, lastName, ordinal, searchKey, signed } from "../lib/format";
import SegmentedControl from "../components/SegmentedControl";
import GapArc from "../components/charts/GapArc";

function PlayerPicker({
  label,
  exclude,
  onPick,
}: {
  label: string;
  exclude: number | null;
  onPick: (id: number) => void;
}) {
  const data = useData();
  const [query, setQuery] = useState("");

  const players = useMemo(() => {
    const byId = new Map<number, LeaderboardRow>();
    for (const season of data.meta.seasons) {
      for (const r of data.leaderboard) {
        if (r.season === season && r.pct !== null) byId.set(r.id, r);
      }
    }
    return [...byId.values()];
  }, [data]);

  const results = useMemo(() => {
    const q = searchKey(query.trim());
    if (q.length < 2) return [];
    return players
      .filter((r) => r.id !== exclude && searchKey(r.name).includes(q))
      .sort((a, b) => b.poss - a.poss)
      .slice(0, 5);
  }, [query, players, exclude]);

  return (
    <div className="relative">
      <p className="font-display text-[11px] font-medium uppercase tracking-wider text-ink-faint">
        {label}
      </p>
      <input
        type="search"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Find a player…"
        aria-label={label}
        className="mt-2 w-full rounded-md border border-line bg-paper px-3 py-2 font-display text-[14px] text-ink placeholder:text-ink-faint focus:border-ink-faint focus:outline-none focus-visible:outline-2 focus-visible:-outline-offset-1 focus-visible:outline-ink"
      />
      {results.length > 0 && (
        <ul className="absolute z-20 mt-1 w-full overflow-hidden rounded-md border border-line bg-paper shadow-sm">
          {results.map((r) => (
            <li key={r.id}>
              <button
                type="button"
                onClick={() => {
                  onPick(r.id);
                  setQuery("");
                }}
                className="flex w-full items-baseline justify-between px-3 py-2 text-left font-display text-[13px] text-ink transition-colors duration-100 hover:bg-wash"
              >
                <span>{r.name}</span>
                <span className="font-mono tnum text-xs text-ink-faint">
                  {r.season}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/** One metric, two players on a shared percentile track. */
function DuelRow({
  label,
  a,
  b,
  aPct,
  bPct,
  aVal,
  bVal,
}: {
  label: string;
  a: string;
  b: string;
  aPct: number | null;
  bPct: number | null;
  aVal: number | null;
  bVal: number | null;
}) {
  if (aPct === null && bPct === null) return null;
  return (
    <div className="grid grid-cols-[4rem_minmax(0,1fr)_4rem] items-center gap-x-3 py-3.5 sm:grid-cols-[5rem_minmax(0,1fr)_5rem]">
      <span
        className="font-mono tnum text-right text-sm"
        style={{ color: aVal !== null ? divergingText(aVal) : undefined }}
      >
        {aVal !== null ? signed(aVal, 1) : "–"}
      </span>
      <div>
        <p className="mb-1.5 text-center font-display text-[11px] font-medium uppercase tracking-wider text-ink-faint">
          {label}
        </p>
        <div className="relative h-2 rounded-full bg-wash">
          <span className="absolute left-1/2 top-1/2 h-3.5 w-px -translate-y-1/2 bg-line" />
          {aPct !== null && aVal !== null && (
            <span
              className="absolute top-1/2 grid h-6 w-6 -translate-x-1/2 -translate-y-1/2 place-items-center rounded-full ring-2 ring-paper transition-[left] duration-700 starting:left-1/2"
              style={{
                left: `${Math.min(100, Math.max(0, aPct))}%`,
                background: divergingColor(aVal),
                transitionTimingFunction: "var(--ease-out-strong)",
              }}
              title={`${a}: ${ordinal(Math.floor(aPct))} %ile`}
            >
              <span className="font-mono text-[10px] font-bold leading-none text-paper">
                {a.slice(0, 1)}
              </span>
            </span>
          )}
          {bPct !== null && bVal !== null && (
            <span
              className="absolute top-1/2 grid h-6 w-6 -translate-x-1/2 -translate-y-1/2 place-items-center rounded-full ring-2 ring-paper transition-[left] duration-700 starting:left-1/2"
              style={{
                left: `${Math.min(100, Math.max(0, bPct))}%`,
                background: divergingColor(bVal),
                transitionTimingFunction: "var(--ease-out-strong)",
                marginTop:
                  aPct !== null && Math.abs(aPct - bPct) < 7 ? 13 : 0,
              }}
              title={`${b}: ${ordinal(Math.floor(bPct))} %ile`}
            >
              <span className="font-mono text-[10px] font-bold leading-none text-paper">
                {b.slice(0, 1)}
              </span>
            </span>
          )}
        </div>
      </div>
      <span
        className="font-mono tnum text-sm"
        style={{ color: bVal !== null ? divergingText(bVal) : undefined }}
      >
        {bVal !== null ? signed(bVal, 1) : "–"}
      </span>
    </div>
  );
}

export default function Compare() {
  const data = useData();
  useTitle("Compare · Over Expected");
  const [params, setParams] = useSearchParams();

  const aId = Number(params.get("a")) || null;
  const bId = Number(params.get("b")) || null;

  const rowsFor = (id: number | null) =>
    id === null
      ? []
      : data.meta.seasons
          .map((s) =>
            data.leaderboard.find(
              (r) => r.id === id && r.season === s && r.pct !== null,
            ),
          )
          .filter((r): r is LeaderboardRow => r !== undefined);

  const aRows = useMemo(() => rowsFor(aId), [aId, data]); // eslint-disable-line react-hooks/exhaustive-deps
  const bRows = useMemo(() => rowsFor(bId), [bId, data]); // eslint-disable-line react-hooks/exhaustive-deps

  const shared = aRows
    .map((r) => r.season)
    .filter((s) => bRows.some((r) => r.season === s));
  const requested = params.get("season");
  const season =
    requested && shared.includes(requested)
      ? requested
      : shared[shared.length - 1] ?? null;

  const a = season ? aRows.find((r) => r.season === season) ?? null : aRows[aRows.length - 1] ?? null;
  const b = season ? bRows.find((r) => r.season === season) ?? null : bRows[bRows.length - 1] ?? null;

  const aChunk = usePlayerChunk(a?.season ?? null);
  const bChunk = usePlayerChunk(b?.season ?? null);
  const aGames =
    a && aChunk.status === "ready" ? aChunk.chunk[String(a.id)]?.games : undefined;
  const bGames =
    b && bChunk.status === "ready" ? bChunk.chunk[String(b.id)]?.games : undefined;

  const update = (patch: Record<string, string>) => {
    const next = new URLSearchParams(params);
    for (const [k, v] of Object.entries(patch)) next.set(k, v);
    setParams(next);
  };

  const aN = a ? lastName(a.name) : "A";
  const bN = b ? lastName(b.name) : "B";

  return (
    <div className="mx-auto max-w-3xl px-5 py-12 sm:px-8 sm:py-16">
      <h1 className="font-display text-3xl font-bold tracking-tight text-ink sm:text-5xl">
        Compare
      </h1>
      <p className="mt-3 max-w-prose text-sm leading-relaxed text-ink-soft sm:text-base">
        Two players, same season, same baseline.
      </p>

      <div className="mt-8 grid gap-6 sm:grid-cols-2">
        {a ? (
          <div className="flex items-center justify-between gap-3 border-b border-line pb-3">
            <span className="flex min-w-0 items-center gap-2.5">
              <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-ink font-mono text-[10px] font-bold text-paper">
                {aN.slice(0, 1)}
              </span>
              <Link
                to={`/player/${a.id}?season=${encodeURIComponent(a.season)}`}
                className="min-w-0 truncate font-display text-xl font-semibold text-ink underline-offset-4 hover:underline"
              >
                {a.name}
              </Link>
            </span>
            <button
              type="button"
              onClick={() => update({ a: "" })}
              className="font-display text-xs text-ink-faint hover:text-ink"
            >
              change
            </button>
          </div>
        ) : (
          <PlayerPicker
            label="Player one"
            exclude={bId}
            onPick={(id) => update({ a: String(id) })}
          />
        )}
        {b ? (
          <div className="flex items-center justify-between gap-3 border-b border-line pb-3">
            <span className="flex min-w-0 items-center gap-2.5">
              <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-ink font-mono text-[10px] font-bold text-paper">
                {bN.slice(0, 1)}
              </span>
              <Link
                to={`/player/${b.id}?season=${encodeURIComponent(b.season)}`}
                className="min-w-0 truncate font-display text-xl font-semibold text-ink underline-offset-4 hover:underline"
              >
                {b.name}
              </Link>
            </span>
            <button
              type="button"
              onClick={() => update({ b: "" })}
              className="font-display text-xs text-ink-faint hover:text-ink"
            >
              change
            </button>
          </div>
        ) : (
          <PlayerPicker
            label="Player two"
            exclude={aId}
            onPick={(id) => update({ b: String(id) })}
          />
        )}
      </div>

      {a && b && (
        <>
          {shared.length > 0 ? (
            <SegmentedControl
              ariaLabel="Season"
              className="mt-8"
              options={shared.map((s) => ({
                value: s,
                label: s,
                shortLabel: `'${s.slice(2, 4)}-${s.slice(5)}`,
              }))}
              value={season ?? shared[shared.length - 1]}
              onChange={(s) => update({ season: s })}
            />
          ) : (
            <p className="mt-8 text-sm text-ink-soft">
              No season where both qualified; showing each player's latest
              qualified season ({a.season} vs {b.season}).
            </p>
          )}

          <div className="mt-6 border-y border-line py-2">
            <DuelRow
              label="FTAOE per 100"
              a={aN}
              b={bN}
              aPct={a.pct}
              bPct={b.pct}
              aVal={a.per100}
              bVal={b.per100}
            />
            <DuelRow
              label="Style-adjusted"
              a={aN}
              b={bN}
              aPct={a.spct}
              bPct={b.spct}
              aVal={a.sper100}
              bVal={b.sper100}
            />
          </div>

          <div className="mt-4 grid grid-cols-2 gap-x-6 text-sm">
            {[a, b].map((p, i) => (
              <p key={i} className="font-mono tnum text-ink-soft">
                {int(p.fta)} <span className="text-ink-faint">FTA vs</span>{" "}
                {p.xfta.toFixed(1)}{" "}
                <span className="text-ink-faint">expected ·</span>{" "}
                {int(p.poss)} <span className="text-ink-faint">poss ·</span>{" "}
                {p.teams.join("/")}
              </p>
            ))}
          </div>

          <div className="mt-10 space-y-8">
            {[
              { row: a, games: aGames },
              { row: b, games: bGames },
            ].map(({ row, games }) => (
              <div key={row.id}>
                <p className="font-display text-sm font-semibold text-ink">
                  {row.name}{" "}
                  <span className="font-mono tnum font-normal" style={{ color: divergingText(row.per100) }}>
                    {signed(row.per100, 1)}
                  </span>
                  <span className="font-mono text-xs text-ink-faint"> · {row.season}</span>
                </p>
                {games ? (
                  <GapArc games={games} height={190} className="mt-2" />
                ) : (
                  <div className="mt-2 h-[190px] animate-pulse rounded bg-wash" />
                )}
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
