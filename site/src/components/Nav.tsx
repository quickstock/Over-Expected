import { Link, NavLink } from "react-router-dom";

const linkClass = ({ isActive }: { isActive: boolean }) =>
  `font-display text-sm font-medium tracking-wide transition-colors duration-150 ${
    isActive ? "text-ink underline underline-offset-4" : "text-ink-soft hover:text-ink"
  }`;

export default function Nav() {
  return (
    <header className="border-b border-line">
      <div className="mx-auto flex max-w-6xl items-baseline justify-between px-5 py-4 sm:px-8">
        <Link
          to="/"
          className="font-display text-lg font-bold tracking-tight text-ink"
        >
          FTAOE
          <span className="ml-2 hidden font-serif text-sm font-normal text-ink-faint sm:inline">
            free throw attempts over expected
          </span>
        </Link>
        <nav className="flex items-baseline gap-5 sm:gap-7">
          <NavLink to="/leaderboard" className={linkClass}>
            Leaderboard
          </NavLink>
          <NavLink to="/methodology" className={linkClass}>
            Methodology
          </NavLink>
        </nav>
      </div>
    </header>
  );
}
