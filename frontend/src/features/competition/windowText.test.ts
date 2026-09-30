import { describe, expect, it } from 'vitest';

import { datesText, sundaysNote, windowInWords, windowTag } from './windowText';

describe('datesText', () => {
  it('drops the year when both dates are in the latest Sunday’s year', () => {
    expect(datesText('2026-08-03', '2026-09-27', '2026-09-27')).toBe('Aug 3 – Sep 27');
  });

  it('spells out both years across a year end, or when the year is not the latest one', () => {
    expect(datesText('2025-09-29', '2026-09-27', '2026-09-27')).toBe('Sep 29, 2025 – Sep 27, 2026');
    expect(datesText('2024-01-07', '2024-12-29', '2026-09-27')).toBe('Jan 7, 2024 – Dec 29, 2024');
    expect(datesText('2026-08-03', '2026-09-27')).toBe('Aug 3, 2026 – Sep 27, 2026');
  });
});

describe('windowTag', () => {
  it('names a preset and its dates', () => {
    expect(windowTag('8w', '2026-08-03', '2026-09-27', '2026-09-27')).toBe(
      'Last 8 weeks · Aug 3 – Sep 27',
    );
    expect(windowTag('ytd', '2026-01-01', '2026-09-27', '2026-09-27')).toBe(
      'This year to date · Jan 1 – Sep 27',
    );
  });

  it('shows a Custom window as its dates alone', () => {
    expect(windowTag('2026-06-01..2026-09-13', '2026-06-01', '2026-09-13', '2026-09-27')).toBe(
      'Jun 1 – Sep 13',
    );
  });
});

describe('windowInWords and sundaysNote', () => {
  it.each([
    ['8w', 'the last 8 weeks'],
    ['3m', 'the last 3 months'],
    ['6m', 'the last 6 months'],
    ['12m', 'the last 12 months'],
    ['ytd', 'this year so far'],
    ['all', 'all time'],
    ['2026-06-01..2026-09-13', 'Jun 1, 2026 – Sep 13, 2026'],
  ] as const)('%s reads "%s"', (window, words) => {
    expect(windowInWords(window)).toBe(words);
  });

  it('falls back to "these dates" for a custom value that does not parse', () => {
    expect(windowInWords('2026-09-13..2026-06-01')).toBe('these dates');
  });

  it('counts the Sundays in plain words', () => {
    expect(sundaysNote(7, '8w')).toBe('Only 7 Sundays in the last 8 weeks.');
    expect(sundaysNote(1, '12m')).toBe('Only 1 Sunday in the last 12 months.');
    expect(sundaysNote(0, 'ytd')).toBe('No Sundays with scores in this year so far.');
  });
});
