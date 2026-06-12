import { Link } from "react-router-dom";
import { useData } from "../data";

export default function Footer() {
  const { meta } = useData();
  const seasons = meta.seasons;
  return (
    <footer className="mt-20 border-t border-line">
      <div className="mx-auto max-w-6xl px-5 py-10 sm:px-8">
        <p className="max-w-2xl text-sm leading-relaxed text-ink-soft">
          FTAOE is descriptive. It blends playstyle, contact-seeking skill, and
          officiating; it does not separate them, and it does not prove
          referee bias. <Link to="/methodology" className="underline underline-offset-2 hover:text-ink">How it works</Link>.
        </p>
        <p className="mt-4 text-xs text-ink-faint">
          Shooting fouls only · {seasons[0]} to {seasons[seasons.length - 1]} ·
          built from possession-level play-by-play ·{" "}
          <Link to="/data" className="underline underline-offset-2 hover:text-ink">
            get the data
          </Link>
        </p>
      </div>
    </footer>
  );
}
