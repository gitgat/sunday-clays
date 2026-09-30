import { describe, expect, it } from 'vitest';
import { rangeText, windowPhrase, windowTagText } from './windowText';

const R = { from: '2026-08-03', to: '2026-09-27' };

describe('windowText', () => {
  it('shows short dates inside one year and full dates across years', () => {
    expect(rangeText(R)).toBe('Aug 3 – Sep 27');
    expect(rangeText({ from: '2025-09-28', to: '2026-09-27' })).toBe('Sep 28, 2025 – Sep 27, 2026');
    expect(rangeText({ from: null, to: '2026-09-27' })).toBe('through Sep 27, 2026');
  });

  it('puts the dates on every preset tag and keeps a custom window as its dates', () => {
    expect(windowTagText('8w', R)).toBe('Last 8 weeks · Aug 3 – Sep 27');
    expect(windowTagText('all', { from: null, to: '2026-09-27' })).toBe(
      'All time · through Sep 27, 2026',
    );
    expect(windowTagText('8w', null)).toBe('Last 8 weeks');
    expect(windowTagText('2026-01-05..2026-02-01', null)).toBe('Jan 5, 2026 – Feb 1, 2026');
  });

  it('reads as a phrase inside a sentence', () => {
    expect(windowPhrase('8w', R)).toBe('the last 8 weeks (Aug 3 – Sep 27)');
    expect(windowPhrase('ytd', { from: '2026-01-01', to: '2026-09-27' })).toBe(
      'this year to date (Jan 1 – Sep 27)',
    );
    expect(windowPhrase('all', { from: null, to: '2026-09-27' })).toBe('all time');
    expect(windowPhrase('12m', null)).toBe('the last 12 months');
    expect(windowPhrase('2026-01-05..2026-02-01', null)).toBe('Jan 5, 2026 – Feb 1, 2026');
  });
});
