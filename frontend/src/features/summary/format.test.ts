import { describe, expect, it } from 'vitest';
import { allStrings, BANNED_WORDS } from '../../test/language';
import { summaryFixture } from './mocks';
import { summaryFilename, summaryLines, windowLine } from './format';

describe('summary card lines', () => {
  it('shows every line when every value is set', () => {
    expect(summaryLines(summaryFixture)).toEqual([
      ['Sundays shot', '11', '(1 special shoot)'],
      ['Rounds · Average', '12 · 41.3', ''],
      ['Best round', '46 · Sep 13', ''],
      ['Personal bests', '1', ''],
      ['Trophies earned', '3', 'Iron Streak — Bronze, Events Attended — Gold, …'],
      ['Longest streak', '6 Sundays in a row', ''],
    ]);
  });

  it('hides zero lines and a streak below 2 (D19)', () => {
    const none = { ...summaryFixture, rounds: 0, average: null, best: null, pbs_set: 0 };
    const quiet = { ...none, trophies: 0, trophy_names: [], longest_streak: 1, special_sundays: 0 };
    expect(summaryLines(quiet)).toEqual([['Sundays shot', '11', '']]);
  });

  it('pluralizes special shoots and lists names without "…" when all are named', () => {
    const lines = summaryLines({
      ...summaryFixture,
      special_sundays: 2,
      trophies: 2,
      trophy_names: ['Doubleheader', 'Iron Streak — Bronze'],
    });
    expect(lines[0]?.[2]).toBe('(2 special shoots)');
    expect(lines[4]?.[2]).toBe('Doubleheader, Iron Streak — Bronze');
  });

  it('names the window: a preset with its dates, All "through", a custom window by dates only', () => {
    expect(windowLine('3m', { from: '2026-07-06', to: '2026-09-27' })).toBe(
      'Last 3 months · Jul 6 – Sep 27',
    );
    expect(windowLine('all', { from: null, to: '2026-09-27' })).toBe(
      'All time · through Sep 27, 2026',
    );
    expect(windowLine('2026-01-04..2026-03-29', { from: '2026-01-04', to: '2026-03-29' })).toBe(
      'Jan 4, 2026 – Mar 29, 2026',
    );
  });

  it('builds the image file name; an open start says "all"', () => {
    expect(summaryFilename('Hadley, Ike', '2026-07-06', '2026-09-27')).toBe(
      'sunday-clays-hadley-ike-2026-07-06-to-2026-09-27.png',
    );
    expect(summaryFilename('Hadley, Ike', null, '2026-09-27')).toBe(
      'sunday-clays-hadley-ike-all-to-2026-09-27.png',
    );
  });

  it('uses no banned word in any line', () => {
    for (const text of allStrings(summaryLines(summaryFixture)))
      expect(text).not.toMatch(BANNED_WORDS);
  });
});
