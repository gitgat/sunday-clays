import { describe, expect, it } from 'vitest';

import {
  boardWindow,
  chartRows,
  formatEventDate,
  formatValue,
  metricLabel,
  oneOf,
  optionalDate,
  optionalOneOf,
  snapIndex,
} from './labels';

describe('chartRows', () => {
  it('keeps unique names and suffixes a display name shared by two shooters with the id', () => {
    expect(
      chartRows([
        { shooter_id: 4, display_name: 'Desmond', value: 12 },
        { shooter_id: 7, display_name: 'Ace, Amy', value: 11 },
        { shooter_id: 9, display_name: 'Desmond', value: 11 },
      ]),
    ).toEqual([
      { display_name: 'Desmond #4', value: 12 },
      { display_name: 'Ace, Amy', value: 11 },
      { display_name: 'Desmond #9', value: 11 },
    ]);
  });
});

describe('formatValue', () => {
  it.each([
    ['avg_score', 43.017, '43.02'],
    ['avg_adjusted', 3.25, '+3.25'],
    ['avg_adjusted', -1.5, '-1.50'],
    ['rating_gain', 1.5, '+1.50'],
    ['wins', 62, '62'],
    ['season_points', 191, '191'],
  ] as const)('%s %d → %s', (metric, value, text) => {
    expect(formatValue(metric, value)).toBe(text);
  });
});

describe('labels', () => {
  it('names metrics for headers', () => {
    expect(metricLabel('season_points')).toBe('Points');
  });

  it('formats ISO event dates without shifting the day', () => {
    expect(formatEventDate('2026-09-27')).toBe('Sep 27, 2026');
    expect(formatEventDate('2025-12-28')).toBe('Dec 28, 2025');
  });
});

describe('snapIndex', () => {
  const dates = ['2026-09-06', '2026-09-13', '2026-09-27'];

  it.each([
    [null, 2],
    ['2026-09-13', 1],
    ['2026-09-20', 1],
    ['2026-01-01', 0],
    ['2027-01-01', 2],
  ])('as_of %s → index %d', (asOf, index) => {
    expect(snapIndex(dates, asOf)).toBe(index);
  });

  it('is 0 without dates', () => {
    expect(snapIndex([], null)).toBe(0);
  });
});

describe('codecs', () => {
  it('oneOf falls back for unknown values', () => {
    const codec = oneOf(['season', 'all_time'] as const, 'season');
    expect(codec.parse('all_time')).toBe('all_time');
    expect(codec.parse('bogus')).toBe('season');
    expect(codec.serialize('all_time')).toBe('all_time');
  });

  it('optionalOneOf maps unknown and empty values to null', () => {
    const codec = optionalOneOf(['member', 'guest'] as const);
    expect(codec.parse('guest')).toBe('guest');
    expect(codec.parse('')).toBeNull();
    expect(codec.serialize(null)).toBe('');
    expect(codec.serialize('member')).toBe('member');
  });

  it('optionalDate accepts only ISO dates', () => {
    expect(optionalDate.parse('2025-12-28')).toBe('2025-12-28');
    expect(optionalDate.parse('12/28/2025')).toBeNull();
    expect(optionalDate.serialize(null)).toBe('');
    expect(optionalDate.serialize('2025-12-28')).toBe('2025-12-28');
  });
});

describe('boardWindow: what each header window asks of the API', () => {
  it.each([
    ['8w', 'season'],
    ['12m', 'rolling_12'],
    ['ytd', 'ytd'],
    ['all', 'all_time'],
  ] as const)('%s uses the %s period with no start date', (window, period) => {
    expect(boardWindow(window, null, '2026-09-27')).toEqual({ period, since: null, asOf: null });
  });

  it('sends a start date for 3M and 6M, counted back from the latest Sunday', () => {
    expect(boardWindow('3m', null, '2026-09-27')).toEqual({
      period: 'season',
      since: '2026-06-28',
      asOf: null,
    });
    expect(boardWindow('6m', null, '2026-09-27')).toEqual({
      period: 'season',
      since: '2026-03-28',
      asOf: null,
    });
  });

  it('counts 3M back from "Board as of", and waits for the latest Sunday when there is none', () => {
    expect(boardWindow('3m', '2026-06-14', '2026-09-27')).toEqual({
      period: 'season',
      since: '2026-03-15',
      asOf: '2026-06-14',
    });
    expect(boardWindow('6m', null, null)).toBeNull();
    expect(boardWindow('3m', '2026-06-14', null)?.since).toBe('2026-03-15');
  });

  it('moves a preset end with "Board as of"', () => {
    expect(boardWindow('ytd', '2025-06-01', '2026-09-27')).toEqual({
      period: 'ytd',
      since: null,
      asOf: '2025-06-01',
    });
  });

  it('gives a Custom window its own start and end', () => {
    expect(boardWindow('2026-01-01..2026-06-30', null, null)).toEqual({
      period: 'season',
      since: '2026-01-01',
      asOf: '2026-06-30',
    });
  });
});
