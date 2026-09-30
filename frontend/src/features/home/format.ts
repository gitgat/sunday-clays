const DAY = new Intl.DateTimeFormat('en-US', {
  month: 'short',
  day: 'numeric',
  year: 'numeric',
  timeZone: 'UTC',
});

/** '2026-09-27' → 'Sep 27, 2026' (UTC in, UTC out: the day never shifts). */
export function formatDay(iso: string): string {
  return DAY.format(new Date(`${iso}T00:00:00Z`));
}

export function round1(value: number): number {
  return Math.round(value * 10) / 10;
}

/** 1st, 2nd, 3rd, 4th … 11th–13th, 21st … */
export function ordinal(n: number): string {
  const mod100 = n % 100;
  if (mod100 >= 11 && mod100 <= 13) return `${n}th`;
  switch (n % 10) {
    case 1:
      return `${n}st`;
    case 2:
      return `${n}nd`;
    case 3:
      return `${n}rd`;
    default:
      return `${n}th`;
  }
}

/** +0.8 / −0.3 (U+2212) / 0.0; rounds before choosing the sign; null → '—'. */
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
