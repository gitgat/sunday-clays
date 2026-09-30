import type { WeatherEvent } from './api';

export type RainFilter = 'any' | 'dry' | 'wet';

export interface ConditionFilters {
  temp: [number, number];
  gustMax: number;
  rain: RainFilter;
}

export interface ConditionSummary {
  events: number;
  meanMedian: number | null;
  meanDifficulty: number | null;
}

export const TEMP_MIN = 20;
export const TEMP_MAX = 100;
export const GUST_MAX = 40;

/** Events inside the slider ranges (a slider at its end is open-ended); `precip_band` decides dry/wet exactly as the server does. */
export function filterEvents(events: WeatherEvent[], filters: ConditionFilters): WeatherEvent[] {
  const [lo, hi] = filters.temp;
  return events.filter(
    (e) =>
      (lo <= TEMP_MIN || e.temp_f >= lo) &&
      (hi >= TEMP_MAX || e.temp_f <= hi) &&
      (filters.gustMax >= GUST_MAX || e.gust_mph <= filters.gustMax) &&
      (filters.rain === 'any' || e.precip_band === filters.rain),
  );
}

function mean(values: (number | null)[]): number | null {
  const known = values.filter((v): v is number => v !== null);
  return known.length === 0 ? null : known.reduce((a, b) => a + b, 0) / known.length;
}

/** Scored events only: mean field median and mean published difficulty. */
export function summarize(events: WeatherEvent[]): ConditionSummary {
  const scored = events.filter((e) => e.has_scores);
  return {
    events: scored.length,
    meanMedian: mean(scored.map((e) => e.median)),
    meanDifficulty: mean(scored.map((e) => e.difficulty)),
  };
}

export const COMPASS = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'] as const;

/** Wind direction in degrees (where the wind comes from) to one of 8 compass sectors. */
export function compassSector(deg: number): (typeof COMPASS)[number] {
  const index = Math.round((((deg % 360) + 360) % 360) / 45) % 8;
  return COMPASS[index] as (typeof COMPASS)[number];
}
