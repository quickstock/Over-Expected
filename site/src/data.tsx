import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import type { PlayerSeasonChunk, SiteData } from "./types";

const DataContext = createContext<SiteData | null>(null);

export function DataProvider({ children }: { children: ReactNode }) {
  const [data, setData] = useState<SiteData | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    fetch(`${import.meta.env.BASE_URL}data.json`)
      .then((r) => {
        if (!r.ok) throw new Error(`${r.status}`);
        return r.json();
      })
      .then(setData)
      .catch(() => setError(true));
  }, []);

  if (error) {
    return (
      <div className="mx-auto max-w-xl px-6 py-32 text-center font-display">
        <p className="text-2xl font-semibold">The data failed to load.</p>
        <p className="mt-3 text-ink-soft">
          Refresh the page. If it keeps happening, the data export is missing.
        </p>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="mx-auto max-w-5xl px-6 py-24" aria-busy="true">
        <div className="h-10 w-72 animate-pulse rounded bg-wash" />
        <div className="mt-6 h-64 animate-pulse rounded bg-wash" />
        <div className="mt-6 h-40 animate-pulse rounded bg-wash" />
      </div>
    );
  }

  return <DataContext.Provider value={data}>{children}</DataContext.Provider>;
}

export function useData(): SiteData {
  const data = useContext(DataContext);
  if (!data) throw new Error("useData outside DataProvider");
  return data;
}

/* ------------------------------------------------------------------ */
/* Per-season player detail, fetched on demand and cached for the     */
/* session. One file per season keeps the initial load small.         */
/* ------------------------------------------------------------------ */

const chunkCache = new Map<string, PlayerSeasonChunk>();
const chunkPromises = new Map<string, Promise<PlayerSeasonChunk>>();

function fetchChunk(season: string): Promise<PlayerSeasonChunk> {
  const cached = chunkPromises.get(season);
  if (cached) return cached;
  const p = fetch(`${import.meta.env.BASE_URL}players-${season}.json`)
    .then((r) => {
      if (!r.ok) throw new Error(`${r.status}`);
      return r.json() as Promise<PlayerSeasonChunk>;
    })
    .then((chunk) => {
      chunkCache.set(season, chunk);
      return chunk;
    })
    .catch((e) => {
      chunkPromises.delete(season); // allow retry on next mount
      throw e;
    });
  chunkPromises.set(season, p);
  return p;
}

export type ChunkState =
  | { status: "loading" }
  | { status: "error" }
  | { status: "ready"; chunk: PlayerSeasonChunk };

export function usePlayerChunk(season: string | null): ChunkState {
  const [, bump] = useState(0);

  useEffect(() => {
    if (!season || chunkCache.has(season)) return;
    let alive = true;
    fetchChunk(season)
      .catch(() => undefined)
      .finally(() => {
        if (alive) bump((n) => n + 1);
      });
    return () => {
      alive = false;
    };
  }, [season]);

  if (!season) return { status: "loading" };
  const chunk = chunkCache.get(season);
  if (chunk) return { status: "ready", chunk };
  if (chunkPromises.has(season)) return { status: "loading" };
  return { status: "error" };
}
