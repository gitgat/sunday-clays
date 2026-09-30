import { describe, expect, it } from 'vitest';
import {
  formatDay,
  formatPct,
  formatScore,
  formatSigned,
  formLabel,
  monthName,
  plural,
  spanText,
} from './format';

describe('formatDay', () => {
  it('formats an ISO date without timezone drift', () => {
    expect(formatDay('2020-01-05')).toBe('Jan 5, 2020');
  });
});

describe('spanText', () => {
  it.each([
    ['2020-01-12', '2020-10-18', 'Jan 12, 2020 – Oct 18, 2020'],
    ['2026-02-01', '2026-02-01', 'Feb 1, 2026'],
    [null, '2026-02-01', '—'],
    ['2026-02-01', null, '—'],
  ])('%s..%s → %s', (first, last, want) => {
    expect(spanText(first, last)).toBe(want);
  });
});

describe('formatSigned', () => {
  it.each([
    [3.44, '+3.4'],
    [-2.06, '−2.1'],
    [0.01, '0.0'],
    [null, '—'],
  ])('%s → %s', (value, want) => {
    expect(formatSigned(value)).toBe(want);
  });
});

describe('formatScore', () => {
  it.each([
    [35.3146, '35.3'],
    [36, '36'],
    [null, '—'],
  ])('%s → %s', (value, want) => {
    expect(formatScore(value)).toBe(want);
  });
});

describe('formatPct', () => {
  it.each([
    [0.183, '18%'],
    [1, '100%'],
    [null, '—'],
  ])('%s → %s', (value, want) => {
    expect(formatPct(value)).toBe(want);
  });
});

describe('monthName', () => {
  it.each([
    [1, 'January'],
    [9, 'September'],
    [12, 'December'],
  ])('%d → %s', (month, want) => {
    expect(monthName(month)).toBe(want);
  });
});

describe('formLabel', () => {
  it.each([
    [3, 'Hot'],
    [2.9, 'Steady'],
    [-2.9, 'Steady'],
    [-3, 'Cold'],
    [null, '—'],
  ])('%s → %s', (form, want) => {
    expect(formLabel(form)).toBe(want);
  });
});

describe('plural', () => {
  it.each([
    [1, 'event', '1 event'],
    [0, 'event', '0 events'],
    [2, 'event', '2 events'],
    [1250, 'clay', '1,250 clays'],
  ])('%d %s → %s', (count, noun, want) => {
    expect(plural(count, noun)).toBe(want);
  });
});
