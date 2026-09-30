const DAY = new Intl.DateTimeFormat('en-US', {
  month: 'short',
  day: 'numeric',
  year: 'numeric',
  timeZone: 'UTC',
});
const MONTH = new Intl.DateTimeFormat('en-US', { month: 'short', timeZone: 'UTC' });

/** '2018-12-30' → 'Dec 30, 2018' (UTC in, UTC out: the day never shifts). */
export function formatDay(iso: string): string {
  return DAY.format(new Date(`${iso}T00:00:00Z`));
}

export function monthShort(month: number): string {
  return MONTH.format(new Date(Date.UTC(2000, month - 1, 1)));
}

export function round1(value: number): number {
  return Math.round(value * 10) / 10;
}

/** Fraction 0–1 → percent with one decimal; null stays null. */
export function pct1(fraction: number | null): number | null {
  return fraction === null ? null : round1(100 * fraction);
}
