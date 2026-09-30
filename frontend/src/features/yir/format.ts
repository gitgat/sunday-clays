const INT = new Intl.NumberFormat('en-US');
const DAY = new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric', timeZone: 'UTC' });
const FULL_DAY = new Intl.DateTimeFormat('en-US', {
  weekday: 'short',
  month: 'short',
  day: 'numeric',
  year: 'numeric',
  timeZone: 'UTC',
});
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

export function formatInt(value: number): string {
  return INT.format(value);
}

export function formatAvg(value: number | null): string {
  return value === null ? '—' : value.toFixed(2);
}

/** "Aug 3" for a calendar date. */
export function formatDay(iso: string): string {
  return DAY.format(new Date(`${iso}T00:00:00Z`));
}

/** "Sun, Sep 28, 2025". */
export function formatFullDay(iso: string): string {
  return FULL_DAY.format(new Date(`${iso}T00:00:00Z`));
}

export function monthName(month: number): string {
  return MONTHS[month - 1] as string;
}

/** " (+74 vs 2024)" style suffix; empty without a previous value. */
export function versus(
  current: number | null,
  previous: number | null,
  year: number,
  digits = 0,
): string {
  if (current === null || previous === null) return '';
  const diff = current - previous;
  const rounded = Number(diff.toFixed(digits));
  const sign = rounded > 0 ? '+' : rounded < 0 ? '−' : '±';
  return ` (${sign}${Math.abs(rounded).toFixed(digits)} vs ${year})`;
}

// A Record index signature: indexing an object literal with a plain `number` is a strict-mode
// error (TS7053), and noUncheckedIndexedAccess makes each lookup `string | undefined`.
const ORDINAL_SUFFIXES: Record<number, string> = { 1: 'st', 2: 'nd', 3: 'rd' };

/** 1 -> "1st", 2 -> "2nd", 11 -> "11th", 23 -> "23rd". */
export function ordinal(n: number): string {
  const tens = n % 100;
  if (tens >= 11 && tens <= 13) return `${n}th`;
  return `${n}${ORDINAL_SUFFIXES[n % 10] ?? 'th'}`;
}

/** "A", "A and B", "A, B and C". */
export function joinNames(names: string[]): string {
  if (names.length <= 1) return names.join('');
  return `${names.slice(0, -1).join(', ')} and ${names[names.length - 1]}`;
}

/**
 * Like `versus`, but only ever an improvement or no change: a named shooter's page celebrates
 * gains and stays quiet about dips.
 */
export function versusGain(
  current: number | null,
  previous: number | null,
  year: number,
  digits = 0,
): string {
  if (current === null || previous === null) return '';
  if (Number(current.toFixed(digits)) < Number(previous.toFixed(digits))) return '';
  return versus(current, previous, year, digits);
}
