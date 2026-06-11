/** Signed with a true minus sign: "+5.9", "−3.2", "0.0" stays unsigned. */
export function signed(value: number, decimals = 1): string {
  const v = value.toFixed(decimals);
  if (parseFloat(v) > 0) return `+${v}`;
  return v.replace("-", "−");
}

export function int(value: number): string {
  return value.toLocaleString("en-US");
}

/** "93rd", "41st", "2nd" */
export function ordinal(value: number): string {
  const n = Math.round(value);
  const rem10 = n % 10;
  const rem100 = n % 100;
  if (rem10 === 1 && rem100 !== 11) return `${n}st`;
  if (rem10 === 2 && rem100 !== 12) return `${n}nd`;
  if (rem10 === 3 && rem100 !== 13) return `${n}rd`;
  return `${n}th`;
}

/** "2024-25" -> "2024-25" (kept as is, single place to change display) */
export function seasonLabel(season: string): string {
  return season;
}

const NAME_SUFFIXES = new Set(["jr", "jr.", "sr", "sr.", "ii", "iii", "iv", "v"]);

/** Display surname: "Jimmy Butler III" -> "Butler", "Gary Trent Jr." -> "Trent" */
export function lastName(full: string): string {
  const parts = full.trim().split(/\s+/);
  let i = parts.length - 1;
  while (i > 0 && NAME_SUFFIXES.has(parts[i].toLowerCase())) i--;
  return parts[i];
}
