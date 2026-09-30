import type { LeaderboardMetric } from './api';

/** Assignable to Plan 07's `Codec<T>` (`useUrlState`); `parse` here never returns null. */
export interface UrlCodec<T> {
  parse: (raw: string) => T;
  serialize: (value: T) => string;
}

export const RACE_TOP = 10;
/** Shooters per frame that fullscreen and the CSV cover (the history endpoint serves up to 500). */
export const RACE_FULL_TOP = 50;
/** Bars the fullscreen race draws (the card draws RACE_TOP). */
export const RACE_FULLSCREEN_TOP = 50;
/** Lines the fullscreen rank chart follows (the card follows RACE_TOP). */
export const BUMP_FULLSCREEN_TOP = 50;

/**
 * How points and standings are counted at each step of the race: the last 12 months, the last 8
 * Sundays, or since 1 January. It never chooses the dates: the header time window does.
 */
export type RaceMode = 'rolling_12' | 'season' | 'ytd';

/** The points rule control, the default (12 months, no reset) first. */
export const RACE_MODES: readonly { value: RaceMode; label: string }[] = [
  { value: 'rolling_12', label: 'Last 12 months' },
  { value: 'season', label: 'Last 8 Sundays' },
  { value: 'ytd', label: 'Since Jan 1' },
];

export const METRICS: readonly { value: LeaderboardMetric; label: string }[] = [
  { value: 'season_points', label: 'Points' },
  { value: 'wins', label: 'Wins' },
  { value: 'podiums', label: 'Podiums' },
  { value: 'avg_score', label: 'Average' },
  { value: 'avg_adjusted', label: 'Avg vs field' },
  { value: 'best_score', label: 'Best round' },
  { value: 'events', label: 'Sundays shot' },
  { value: 'rounds', label: 'Rounds' },
  { value: 'rating_gain', label: 'Rating gain' },
];

export function metricLabel(metric: LeaderboardMetric): string {
  return METRICS.find((m) => m.value === metric)?.label ?? metric;
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

export function oneOf<T extends string>(values: readonly T[], fallback: T): UrlCodec<T> {
  const isMember = (raw: string): raw is T => (values as readonly string[]).includes(raw);
  return {
    parse: (raw) => (isMember(raw) ? raw : fallback),
    serialize: (value) => value,
  };
}
