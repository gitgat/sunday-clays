import { describe, expect, it } from 'vitest';
import { formatDay, monthShort, pct1, round1 } from './format';

describe('club formatting', () => {
  it('formats ISO dates without timezone drift', () => {
    expect(formatDay('2018-12-30')).toBe('Dec 30, 2018');
  });

  it.each([
    [1, 'Jan'],
    [9, 'Sep'],
    [12, 'Dec'],
  ])('month %d → %s', (month, want) => {
    expect(monthShort(month)).toBe(want);
  });

  it.each([
    [2.25, 2.3],
    [-1.44, -1.4],
    [7, 7],
  ])('round1(%d) → %d', (value, want) => {
    expect(round1(value)).toBe(want);
  });

  it.each([
    [0.4567, 45.7],
    [0, 0],
    [null, null],
  ])('pct1(%s) → %s', (value, want) => {
    expect(pct1(value)).toBe(want);
  });
});
