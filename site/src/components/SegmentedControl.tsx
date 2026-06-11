interface Option {
  value: string;
  label: string;
  /** Compact label below the sm breakpoint (e.g. "'24-25"). */
  shortLabel?: string;
}

export default function SegmentedControl({
  options,
  value,
  onChange,
  ariaLabel,
  className = "",
}: {
  options: Option[];
  value: string;
  onChange: (value: string) => void;
  ariaLabel: string;
  className?: string;
}) {
  return (
    <div
      role="group"
      aria-label={ariaLabel}
      className={`inline-flex items-stretch overflow-hidden rounded-md border border-line ${className}`}
    >
      {options.map((o, i) => (
        <button
          key={o.value}
          type="button"
          aria-pressed={o.value === value}
          onClick={() => onChange(o.value)}
          className={`group px-2.5 py-1.5 font-display text-[13px] font-medium transition-colors duration-150 focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-ink sm:px-3 ${
            o.value === value
              ? "bg-ink text-paper"
              : "bg-paper text-ink-soft hover:bg-wash hover:text-ink"
          } ${i > 0 ? "border-l border-line" : ""}`}
        >
          <span className="inline-block transition-transform duration-150 group-active:scale-[0.94]">
            {o.shortLabel ? (
              <>
                <span className="sm:hidden">{o.shortLabel}</span>
                <span className="hidden sm:inline">{o.label}</span>
              </>
            ) : (
              o.label
            )}
          </span>
        </button>
      ))}
    </div>
  );
}
