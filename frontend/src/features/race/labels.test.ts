import { describe, expect, it } from 'vitest';

import { RACE_MODES, formatEventDate, formatValue, metricLabel, oneOf } from './labels';

describe('race labels', () => {
  it('lists the points rules, the last 12 months first (it never resets)', () => {
    expect(RACE_MODES.map((m) => m.value)).toEqual(['rolling_12', 'season', 'ytd']);
    expect(RACE_MODES.map((m) => m.label)).toEqual([
      'Last 12 months',
      'Last 8 Sundays',
      'Since Jan 1',
    ]);
  });

  it('falls back for unknown enum values', () => {
    const codec = oneOf(['season', 'all_time'] as const, 'season');
    expect(codec.parse('all_time')).toBe('all_time');
    expect(codec.parse('nope')).toBe('season');
    expect(codec.serialize('season')).toBe('season');
  });

  it.each([
    ['season_points', 191, '191'],
    ['avg_score', 43.017, '43.02'],
    ['rating_gain', 2.5, '+2.50'],
    ['avg_adjusted', -1, '-1.00'],
  ] as const)('formats %s %d as %s', (metric, value, text) => {
    expect(formatValue(metric, value)).toBe(text);
  });

  it('labels metrics and dates', () => {
    expect(metricLabel('wins')).toBe('Wins');
    expect(formatEventDate('2026-09-27')).toBe('Sep 27, 2026');
  });

  it('falls back to the raw key for a metric the page does not list', () => {
    // A metric the API adds later still gets a readable label instead of nothing.
    expect(metricLabel('brand_new' as never)).toBe('brand_new');
  });
});
