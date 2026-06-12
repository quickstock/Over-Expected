import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useData } from "../data";
import type { LeaderboardRow } from "../types";
import { Delta } from "./Delta";
import { int, searchKey } from "../lib/format";

/**
 * Global player search. Cmd/Ctrl+K or the nav button opens it; type a
 * few letters, arrow keys + Enter to jump to a player page. Shows each
 * player's latest qualified season.
 */
export default function CommandK({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const data = useData();
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  // Latest qualified season per player.
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
      .filter((r) => searchKey(r.name).includes(q))
      .sort((a, b) => b.poss - a.poss)
      .slice(0, 8);
  }, [query, players]);

  useEffect(() => {
    if (open) {
      setQuery("");
      setActive(0);
      requestAnimationFrame(() => inputRef.current?.focus());
    }
  }, [open]);

  useEffect(() => setActive(0), [results.length]);

  if (!open) return null;

  const go = (r: LeaderboardRow) => {
    onClose();
    navigate(`/player/${r.id}?season=${encodeURIComponent(r.season)}`);
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center bg-ink/20 px-4 pt-[12vh] backdrop-blur-[2px]"
      role="dialog"
      aria-modal="true"
      aria-label="Find a player"
      onClick={onClose}
    >
      <div
        className="w-full max-w-md overflow-hidden rounded-lg border border-line bg-paper shadow-lg transition-[opacity,transform] duration-200 starting:translate-y-2 starting:opacity-0"
        style={{ transitionTimingFunction: "var(--ease-out-strong)" }}
        onClick={(e) => e.stopPropagation()}
      >
        <input
          ref={inputRef}
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Escape") onClose();
            if (e.key === "ArrowDown") {
              e.preventDefault();
              setActive((a) => Math.min(a + 1, results.length - 1));
            }
            if (e.key === "ArrowUp") {
              e.preventDefault();
              setActive((a) => Math.max(a - 1, 0));
            }
            if (e.key === "Enter" && results[active]) go(results[active]);
          }}
          placeholder="Find a player…"
          aria-label="Find a player"
          className="w-full border-b border-line bg-paper px-4 py-3.5 font-display text-[15px] text-ink placeholder:text-ink-faint focus:outline-none"
        />
        {results.length > 0 && (
          <ul className="max-h-80 overflow-y-auto py-1">
            {results.map((r, i) => (
              <li key={r.id}>
                <button
                  type="button"
                  onClick={() => go(r)}
                  onPointerEnter={() => setActive(i)}
                  className={`flex w-full items-baseline justify-between gap-3 px-4 py-2.5 text-left transition-colors duration-100 ${
                    i === active ? "bg-wash" : ""
                  }`}
                >
                  <span className="min-w-0">
                    <span className="block truncate font-display text-[15px] font-semibold text-ink">
                      {r.name}
                    </span>
                    <span className="block text-xs text-ink-soft">
                      {r.season} · {r.teams.join(" · ")} · {int(r.poss)} poss
                    </span>
                  </span>
                  <Delta per100={r.per100} className="text-base" />
                </button>
              </li>
            ))}
          </ul>
        )}
        {query.trim().length >= 2 && results.length === 0 && (
          <p className="px-4 py-6 text-center text-sm text-ink-faint">
            No qualified player matches.
          </p>
        )}
      </div>
    </div>
  );
}
