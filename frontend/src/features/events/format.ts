const DAY = new Intl.DateTimeFormat('en-US', {
  month: 'short',
  day: 'numeric',
  year: 'numeric',
  timeZone: 'UTC',
});

const ROUND_TYPE_LABELS: Record<string, string> = {
  sporting: 'Sporting',
  super_sporting: 'Super Sporting',
};

/** '2026-09-13' → 'Sep 13, 2026'. Parsed as UTC midnight and formatted in UTC, so the day never shifts. */
export function formatDay(iso: string): string {
  return DAY.format(new Date(`${iso}T00:00:00Z`));
}

export function roundTypeLabel(roundType: string): string {
  return ROUND_TYPE_LABELS[roundType] ?? roundType;
}

/** +1.5 / −0.8 (U+2212) / 0.0; rounds before choosing the sign; null → '—'. */
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

/** Published difficulty: positive = harder than a typical Sunday of the past year (C7). Words for the tile's hint. */
export function difficultyHint(difficulty: number | null): string | undefined {
  if (difficulty === null) return undefined;
  const text = formatSigned(difficulty);
  if (text === '0.0') return 'a typical Sunday';
  return difficulty > 0 ? 'harder than a typical Sunday' : 'easier than a typical Sunday';
}

/** The nearest earlier and later Sunday with scores around `date` (which need not be one itself). */
export function neighbourSundays(
  sundays: readonly { event_date: string; has_scores: boolean }[],
  date: string,
): { prev: string | null; next: string | null } {
  let prev: string | null = null;
  let next: string | null = null;
  for (const { event_date, has_scores } of sundays) {
    if (!has_scores) continue;
    if (event_date < date && (prev === null || event_date > prev)) prev = event_date;
    if (event_date > date && (next === null || event_date < next)) next = event_date;
  }
  return { prev, next };
}

/** Regular Sundays are out of 50 (the weekly workbook's rounds). */
const REGULAR_TARGETS = 50;

/** Plan 17: a special shoot. Payloads from before Plan 17 omit `kind`; they are regular. */
export function isSpecial(e: { kind?: string }): boolean {
  return e.kind === 'special';
}

/** Targets a round on this Sunday is out of. */
export function targetsOf(e: { target_total?: number }): number {
  return e.target_total ?? REGULAR_TARGETS;
}

/** "Special · 60": the tag a special shoot carries wherever it is listed. */
export function specialTag(e: { target_total?: number }): string {
  return `Special · ${targetsOf(e)}`;
}

/** The special shoot's name ("3-Bird Shoot"), or null when the sheet gave none. */
export function specialName(e: { label?: string | null }): string | null {
  const label = e.label?.trim() ?? '';
  return label === '' ? null : label;
}
