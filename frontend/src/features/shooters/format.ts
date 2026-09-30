const DAY = new Intl.DateTimeFormat('en-US', {
  month: 'short',
  day: 'numeric',
  year: 'numeric',
  timeZone: 'UTC',
});
const MONTH = new Intl.DateTimeFormat('en-US', { month: 'long', timeZone: 'UTC' });

/** '2020-01-05' → 'Jan 5, 2020' (UTC in, UTC out: the day never shifts). */
export function formatDay(iso: string): string {
  return DAY.format(new Date(`${iso}T00:00:00Z`));
}

export function spanText(first: string | null, last: string | null): string {
  if (first === null || last === null) return '—';
  return first === last ? formatDay(first) : `${formatDay(first)} – ${formatDay(last)}`;
}

/** +3.4 / −2.1 (U+2212) / 0.0; rounds before choosing the sign; null → '—'. */
export function formatSigned(value: number | null, digits = 1): string {
  if (value === null) return '—';
  const rounded = Number(value.toFixed(digits));
  if (rounded === 0) return (0).toFixed(digits);
  const magnitude = Math.abs(rounded).toFixed(digits);
  return rounded > 0 ? `+${magnitude}` : `−${magnitude}`;
}

export function formatScore(value: number | null): string {
  if (value === null) return '—';
  return Number.isInteger(value) ? String(value) : value.toFixed(1);
}

/** Fraction 0–1 → whole percent. */
export function formatPct(fraction: number | null): string {
  return fraction === null ? '—' : `${Math.round(fraction * 100)}%`;
}

/** 1 → '1 Sunday', 0 or 2 → '0 Sundays' / '2 Sundays'; thousands grouped ('1,250 clays'). Regular nouns only. */
export function plural(count: number, noun: string): string {
  return `${count.toLocaleString('en-US')} ${count === 1 ? noun : `${noun}s`}`;
}

export function monthName(month: number): string {
  return MONTH.format(new Date(Date.UTC(2000, month - 1, 1)));
}

/** Plan 06 T8: form = mean residual of the last 5 rounds; hot ≥ +3, cold ≤ −3. */
export function formLabel(form: number | null): string {
  if (form === null) return '—';
  if (form >= 3) return 'Hot';
  if (form <= -3) return 'Cold';
  return 'Steady';
}

/** Small-sample guards (owner ruling 2026-09-29): below these a number is shown as "not enough rounds yet". */
export const MIN_FLOOR_ROUNDS = 8;
export const MIN_RUST_ROUNDS = 3;
export const MIN_CLUB_SHOOTERS = 3;

export const NOT_ENOUGH = 'Not enough rounds yet';

/** A personal best needs this many rounds on earlier days (the trophy rule); a best before that is "early". */
export const MIN_PB_EARLIER_ROUNDS = 5;
