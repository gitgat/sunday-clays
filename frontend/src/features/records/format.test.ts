import { describe, expect, it } from 'vitest';

import { chartRows, formatEventDate, formatRating, formatSigned, labelIds } from './format';

describe('chartRows', () => {
  it('keeps unique names and suffixes a display name shared by two shooters with the id', () => {
    expect(
      chartRows([
        { shooter_id: 4, display_name: 'Desmond', value: 12 },
        { shooter_id: 7, display_name: 'Ace, Amy', value: 11 },
        { shooter_id: 9, display_name: 'Desmond', value: 11 },
      ]),
    ).toEqual([
      { display_name: 'Desmond #4', value: 12, shooter_id: 4 },
      { display_name: 'Ace, Amy', value: 11, shooter_id: 7 },
      { display_name: 'Desmond #9', value: 11, shooter_id: 9 },
    ]);
  });

  it('maps each chart label back to its shooter id', () => {
    const labels = labelIds([
      { shooter_id: 4, display_name: 'Desmond', value: 12 },
      { shooter_id: 7, display_name: 'Ace, Amy', value: 11 },
      { shooter_id: 9, display_name: 'Desmond', value: 11 },
    ]);
    expect(Object.fromEntries(labels)).toEqual({ 'Desmond #4': 4, 'Ace, Amy': 7, 'Desmond #9': 9 });
  });
});

describe('records formatting', () => {
  it('formats ISO dates without shifting the day', () => {
    expect(formatEventDate('2021-01-17')).toBe('Jan 17, 2021');
  });

  it.each([
    [18, '+18.0'],
    [-5.5, '-5.5'],
    [0, '0.0'],
  ])('signs %d as %s', (value, text) => {
    expect(formatSigned(value)).toBe(text);
  });

  it('shows ratings to one decimal', () => {
    expect(formatRating(47.256)).toBe('47.3');
  });
});
