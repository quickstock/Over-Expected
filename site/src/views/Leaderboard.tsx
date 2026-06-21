import { useSearchParams } from "react-router-dom";
import { useTitle } from "../lib/useTitle";
import SegmentedControl from "../components/SegmentedControl";
import FoulDrawingBoard from "./boards/FoulDrawingBoard";
import ShotValueBoard from "./boards/ShotValueBoard";

type Lens = "value" | "making" | "fouls";

const LENS_OPTS: { value: Lens; label: string; shortLabel: string }[] = [
  { value: "value", label: "Shot value", shortLabel: "Value" },
  { value: "making", label: "Shot-making", shortLabel: "Making" },
  { value: "fouls", label: "Foul-drawing", shortLabel: "Fouls" },
];
const LENS_TITLE: Record<Lens, string> = {
  value: "Shot value · Over Expected",
  making: "Shot-making · Over Expected",
  fouls: "Foul-drawing · Over Expected",
};

/**
 * The leaderboard, switchable across three lenses on the same player pool:
 * combined shot value (points over expected), shot-making only (FG points
 * over expected), and foul-drawing only (the original FTAOE board). The lens
 * lives in the URL; each board owns its own season/sort/filter state.
 */
export default function Leaderboard() {
  const [params, setParams] = useSearchParams();
  const lens = (LENS_OPTS.some((o) => o.value === params.get("lens"))
    ? params.get("lens")
    : "value") as Lens;
  useTitle(LENS_TITLE[lens]);

  const lensControl = (
    <SegmentedControl
      ariaLabel="Metric"
      options={LENS_OPTS}
      value={lens}
      onChange={(l) => {
        // Whole-board swap: drop the prior lens's sort/dir so each board
        // falls back to its own headline metric.
        const next = new URLSearchParams(params);
        next.set("lens", l);
        next.delete("sort");
        next.delete("dir");
        setParams(next, { replace: false });
      }}
    />
  );

  return lens === "fouls" ? (
    <FoulDrawingBoard lensControl={lensControl} />
  ) : (
    <ShotValueBoard lens={lens} lensControl={lensControl} />
  );
}
