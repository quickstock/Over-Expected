interface Option {
  value: string;
  label: string;
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
          className={`px-3 py-1.5 font-display text-[13px] font-medium transition-colors duration-150 focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-ink ${
            o.value === value
              ? "bg-ink text-paper"
              : "bg-paper text-ink-soft hover:bg-wash hover:text-ink"
          } ${i > 0 ? "border-l border-line" : ""}`}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}
