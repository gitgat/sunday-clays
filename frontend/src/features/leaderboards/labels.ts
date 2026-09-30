import type { TabularRow } from '../../components/charts/types';
import {
  parseCustomWindow,
  windowRange,
  type TimeWindow,
  type TimeWindowPreset,
} from '../../lib/timeWindowChoice';
import type { LeaderboardMetric, LeaderboardPeriod, ShooterStatus } from './api';

/** Assignable to Plan 07's `Codec<T>` (`useUrlState`); `parse` here never returns null. */
export interface UrlCodec<T> {
  parse: (raw: string) => T;
  serialize: (value: T) => string;
}

export interface Option<T> {
  value: T;
  label: string;
}

/** The API period each header window preset is asked for (3M, 6M and Custom send a start date instead). */
const PRESET_PERIODS: Partial<Record<TimeWindowPreset, LeaderboardPeriod>> = {
  '8w': 'season',
  '12m': 'rolling_12',
  ytd: 'ytd',
  all: 'all_time',
};

export interface BoardWindow {
  period: LeaderboardPeriod;
  /** A start date: 3M, 6M and Custom boards run from here (the period is then ignored). */
  since: string | null;
  /** The last day counted; null lets the server pick the latest scored Sunday. */
  asOf: string | null;
}

/**
 * What a header window asks of GET /api/leaderboards. 8W, 12M, YTD and All use the season, rolling-12,
 * year-to-date and all-time rules (and their minimum rounds); 3M, 6M and Custom send since/as_of, and the
 * server picks the matching minimum-rounds rule. `asOf` (the "Board as of" date) moves a preset's end
 * only; a Custom window keeps its own end. Null while 3M or 6M cannot be dated yet (no latest Sunday).
 */
export function boardWindow(
  window: TimeWindow,
  asOf: string | null,
  latest: string | null,
): BoardWindow | null {
  const custom = parseCustomWindow(window);
  if (custom !== null) return { period: 'season', since: custom.from, asOf: custom.to };
  const preset = window as TimeWindowPreset;
  const period = PRESET_PERIODS[preset];
  if (period !== undefined) return { period, since: null, asOf };
  const end = asOf ?? latest;
  if (end === null) return null;
  return { period: 'season', since: windowRange(preset, end).from, asOf };
}

export const METRICS: readonly Option<LeaderboardMetric>[] = [
  { value: 'avg_score', label: 'Average' },
  { value: 'avg_adjusted', label: 'Avg vs field' },
  { value: 'best_score', label: 'Best round' },
  { value: 'wins', label: 'Wins' },
  { value: 'podiums', label: 'Podiums' },
  { value: 'events', label: 'Sundays shot' },
  { value: 'rounds', label: 'Rounds' },
  { value: 'rating_gain', label: 'Rating gain' },
  { value: 'season_points', label: 'Points' },
];

export const STATUSES: readonly Option<ShooterStatus>[] = [
  { value: 'member', label: 'Members' },
  { value: 'guest', label: 'Guests' },
  { value: 'deceased', label: 'In memoriam' },
];

export const GAUGES: readonly Option<string>[] = [
  { value: '12 Gauge', label: '12 gauge' },
  { value: '20 Gauge', label: '20 gauge' },
  { value: '28 Gauge', label: '28 gauge' },
  { value: '.410', label: '.410' },
  { value: 'Sub-Gauge', label: 'Sub-gauge' },
  { value: 'SxS', label: 'SxS' },
  { value: 'unspecified', label: 'Not recorded' },
];

/** Rating gain ignores the round-type and gauge filters (C7). */
export const RATING_METRICS: readonly LeaderboardMetric[] = ['rating_gain'];

// METRICS lists every metric, so every key is present.
const METRIC_LABELS = Object.fromEntries(METRICS.map((m) => [m.value, m.label])) as Record<
  LeaderboardMetric,
  string
>;

/** The standings' count column: Sundays for the Sunday-based boards, rounds for the rest. */
export function countLabel(metric: LeaderboardMetric): 'Sundays' | 'Rounds' {
  return metric === 'season_points' || metric === 'events' ? 'Sundays' : 'Rounds';
}

export function metricLabel(metric: LeaderboardMetric): string {
  return METRIC_LABELS[metric];
}

/**
 * Bar-chart rows. `barOption` keeps one category per distinct label, so a display name held by two shooters (e.g.
 * first-name-only guests) is charted as `<name> #<id>`, as Plan 07's `race.ts` does (Plan 07 D18).
 */
export function chartRows(
  rows: readonly { shooter_id: number; display_name: string; value: number }[],
): TabularRow[] {
  const names = rows.map((row) => row.display_name);
  return rows.map((row) => ({
    display_name:
      names.indexOf(row.display_name) === names.lastIndexOf(row.display_name)
        ? row.display_name
        : `${row.display_name} #${String(row.shooter_id)}`,
    value: row.value,
  }));
}

export function formatValue(metric: LeaderboardMetric, value: number): string {
  switch (metric) {
    case 'avg_score':
      return value.toFixed(2);
    case 'avg_adjusted':
    case 'rating_gain':
      return `${value > 0 ? '+' : ''}${value.toFixed(2)}`;
    default:
      return String(Math.round(value));
  }
}

export function formatEventDate(iso: string): string {
  return new Date(`${iso}T00:00:00Z`).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    timeZone: 'UTC',
  });
}

/** Index of the last event date on or before `asOf`; `null` means the latest event. */
export function snapIndex(dates: readonly string[], asOf: string | null): number {
  if (asOf === null) return Math.max(0, dates.length - 1);
  let index = 0;
  dates.forEach((date, i) => {
    if (date <= asOf) index = i;
  });
  return index;
}

export function oneOf<T extends string>(values: readonly T[], fallback: T): UrlCodec<T> {
  const isMember = (raw: string): raw is T => (values as readonly string[]).includes(raw);
  return {
    parse: (raw) => (isMember(raw) ? raw : fallback),
    serialize: (value) => value,
  };
}

export function optionalOneOf<T extends string>(values: readonly T[]): UrlCodec<T | null> {
  const isMember = (raw: string): raw is T => (values as readonly string[]).includes(raw);
  return {
    parse: (raw) => (isMember(raw) ? raw : null),
    serialize: (value) => value ?? '',
  };
}

export const optionalDate: UrlCodec<string | null> = {
  parse: (raw) => (/^\d{4}-\d{2}-\d{2}$/.test(raw) ? raw : null),
  serialize: (value) => value ?? '',
};
