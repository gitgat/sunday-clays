import { describe, expect, it } from 'vitest';
import { CATEGORIES, CATEGORY_LABELS, formatCount, formatPct, trophyTitle } from './labels';

describe('labels', () => {
  it('titles tier trophies with their label and one-offs with their name', () => {
    expect(trophyTitle({ name: 'Clays Broken', label: '1,000 clays broken' })).toBe(
      'Clays Broken — 1,000 clays broken',
    );
    expect(trophyTitle({ name: 'First Win', label: null })).toBe('First Win');
  });

  it('lists the categories in the backend Category order with their labels', () => {
    expect(CATEGORIES.map((c) => CATEGORY_LABELS[c])).toEqual([
      'Milestones',
      'Scoring',
      'Calendar',
      'Conditions',
      'Stations',
      'Competition',
    ]);
  });

  it('formats counts and percentages', () => {
    expect(formatCount(1742)).toBe('1,742');
    expect(formatCount(2.6)).toBe('3');
    expect(formatPct(19.56)).toBe('19.6%');
  });
});
