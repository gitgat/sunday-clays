import { describe, expect, it } from 'vitest';
import {
  difficultyHint,
  formatDay,
  formatScore,
  formatSigned,
  neighbourSundays,
  roundTypeLabel,
} from './format';

describe('formatDay', () => {
  it.each([
    ['2026-09-13', 'Sep 13, 2026'],
    ['2018-12-30', 'Dec 30, 2018'],
    ['2020-01-05', 'Jan 5, 2020'],
  ])('%s → %s without timezone drift', (iso, want) => {
    expect(formatDay(iso)).toBe(want);
  });
});

describe('formatSigned', () => {
  it.each([
    [1.46, 1, '+1.5'],
    [-0.84, 1, '−0.8'],
    [-0.04, 1, '0.0'],
    [0, 1, '0.0'],
    [3, 0, '+3'],
    [-11, 0, '−11'],
  ])('%d with %d digits → %s', (value, digits, want) => {
    expect(formatSigned(value, digits)).toBe(want);
  });

  it('renders null as an em dash', () => {
    expect(formatSigned(null)).toBe('—');
  });
});

describe('roundTypeLabel', () => {
  it.each([
    ['sporting', 'Sporting'],
    ['super_sporting', 'Super Sporting'],
    ['unknown', 'unknown'], // not a round type: passed through as is
    ['trap', 'trap'],
  ])('%s → %s', (value, want) => {
    expect(roundTypeLabel(value)).toBe(want);
  });
});

describe('formatScore', () => {
  it.each([
    [36, '36'],
    [40.5, '40.5'],
    [null, '—'],
  ])('%s → %s', (value, want) => {
    expect(formatScore(value)).toBe(want);
  });
});

describe('difficultyHint', () => {
  it.each([
    [1.23, 'harder than a typical Sunday'],
    [-0.8, 'easier than a typical Sunday'],
    [0.02, 'a typical Sunday'],
    [null, undefined],
  ])('%s → %s', (value, want) => {
    expect(difficultyHint(value)).toBe(want);
  });
});

describe('neighbourSundays', () => {
  const sundays = [
    { event_date: '2026-09-06', has_scores: true },
    { event_date: '2026-09-13', has_scores: false },
    { event_date: '2026-09-20', has_scores: true },
    { event_date: '2026-09-27', has_scores: true },
  ];

  it('finds the nearest scored Sundays either side, skipping unscored ones', () => {
    expect(neighbourSundays(sundays, '2026-09-20')).toEqual({
      prev: '2026-09-06',
      next: '2026-09-27',
    });
  });

  it('has no previous before the first and no next after the last', () => {
    expect(neighbourSundays(sundays, '2026-09-06').prev).toBeNull();
    expect(neighbourSundays(sundays, '2026-09-27').next).toBeNull();
  });

  it('works from a date that is not in the list, whatever order the list is in', () => {
    expect(neighbourSundays([...sundays].reverse(), '2026-09-14')).toEqual({
      prev: '2026-09-06',
      next: '2026-09-20',
    });
  });
});
