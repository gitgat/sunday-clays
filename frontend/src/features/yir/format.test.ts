import { describe, expect, it } from 'vitest';
import {
  formatAvg,
  formatDay,
  formatInt,
  joinNames,
  monthName,
  ordinal,
  versus,
  versusGain,
} from './format';

describe('year in review formatting', () => {
  it('formats numbers and dates', () => {
    expect(formatInt(44683)).toBe('44,683');
    expect(formatAvg(35.2668)).toBe('35.27');
    expect(formatAvg(null)).toBe('—');
    expect(formatDay('2025-08-03')).toBe('Aug 3');
    expect(monthName(1)).toBe('Jan');
    expect(monthName(12)).toBe('Dec');
  });

  it('compares with the previous year', () => {
    expect(versus(1267, 1193, 2024)).toBe(' (+74 vs 2024)');
    expect(versus(23, 26, 2024)).toBe(' (−3 vs 2024)');
    expect(versus(48, 48, 2024)).toBe(' (±0 vs 2024)');
    expect(versus(35.2668, 34.4409, 2024, 2)).toBe(' (+0.83 vs 2024)');
    expect(versus(10, null, 2024)).toBe('');
    expect(versus(null, 10, 2024)).toBe('');
  });

  it('only reports a gain or no change for a named shooter', () => {
    expect(versusGain(26, 23, 2024)).toBe(' (+3 vs 2024)');
    expect(versusGain(23, 23, 2024)).toBe(' (±0 vs 2024)');
    expect(versusGain(20, 23, 2024)).toBe('');
    expect(versusGain(41.9, 42, 2024, 1)).toBe('');
    expect(versusGain(null, 23, 2024)).toBe('');
    expect(versusGain(23, null, 2024)).toBe('');
  });

  it('writes Quigley ordinals', () => {
    expect([1, 2, 3, 4, 11, 12, 13, 19, 21, 22, 23, 111].map(ordinal)).toEqual([
      '1st',
      '2nd',
      '3rd',
      '4th',
      '11th',
      '12th',
      '13th',
      '19th',
      '21st',
      '22nd',
      '23rd',
      '111th',
    ]);
  });

  it('joins names in plain Quigley', () => {
    expect(joinNames([])).toBe('');
    expect(joinNames(['A'])).toBe('A');
    expect(joinNames(['A', 'B'])).toBe('A and B');
    expect(joinNames(['A', 'B', 'C'])).toBe('A, B and C');
  });
});
