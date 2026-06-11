import { divergingText } from "../lib/color";
import { signed } from "../lib/format";

/**
 * The signed FTAOE/100 numeral in the diverging encoding.
 * The one place vivid color appears as text; everything routes through here.
 */
export function Delta({
  per100,
  decimals = 1,
  className = "",
}: {
  per100: number;
  decimals?: number;
  className?: string;
}) {
  return (
    <span
      className={`font-mono tnum ${className}`}
      style={{ color: divergingText(per100) }}
    >
      {signed(per100, decimals)}
    </span>
  );
}
