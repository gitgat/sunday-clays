import { describe, expect, it } from 'vitest';
import { formatDay, formatScore, formatSigned, ordinal, round1 } from './format';

describe('home formatting', () => {
  it('formats ISO dates without timezone drift', () => {
    expect(formatDay('2026-09-27')).toBe('Sep 27, 2026');
  });

  it.each([
    [1, '1st'],
    [2, '2nd'],
    [3, '3rd'],
    [4, '4th'],
    [11, '11th'],
    [12, '12th'],
    [13, '13th'],
    [16, '16th'],
    [21, '21st'],
    [22, '22nd'],
    [23, '23rd'],
    [101, '101st'],
    [111, '111th'],
  ])('ordinal(%d) → %s', (n, want) => {
    expect(ordinal(n)).toBe(want);
  });

  it.each([
    [0.84, '+0.8'],
    [-0.3, '−0.3'],
    [0.04, '0.0'],
    [null, '—'],
  ])('formatSigned(%s) → %s', (value, want) => {
    expect(formatSigned(value)).toBe(want);
  });

  it.each([
    [39, '39'],
    [40.5, '40.5'],
    [null, '—'],
  ])('formatScore(%s) → %s', (value, want) => {
    expect(formatScore(value)).toBe(want);
  });

  it('round1 rounds to one decimal', () => {
    expect(round1(23.46)).toBe(23.5);
  });
});
