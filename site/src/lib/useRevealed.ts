import { useEffect, useState } from "react";
import type { RefObject } from "react";

/**
 * True once the referenced element scrolls into view (once, then disconnects)
 * the draw-on-reveal trigger shared by the charts. Honors reduced motion by
 * starting revealed, so no entrance transition ever plays for those users.
 */
export function useRevealed(
  ref: RefObject<HTMLElement | null>,
  threshold = 0.25,
): boolean {
  const [revealed, setRevealed] = useState(
    () =>
      typeof window !== "undefined" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches,
  );

  useEffect(() => {
    if (revealed || !ref.current) return;
    const io = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting) {
          setRevealed(true);
          io.disconnect();
        }
      },
      { threshold },
    );
    io.observe(ref.current);
    return () => io.disconnect();
  }, [revealed, threshold, ref]);

  return revealed;
}
