import { describe, expect, it } from 'vitest';
import { pct, percentValue, signedPoints } from './format';

describe('format', () => {
  it('formats fractions as percentages with a dash for missing values', () => {
    expect(pct(0.501931)).toBe('50.19%');
    expect(pct(0)).toBe('0.00%');
    expect(pct(null)).toBe('—');
  });

  it('formats deltas as signed percentage points', () => {
    expect(signedPoints(0.048)).toBe('+4.80 pts');
    expect(signedPoints(-0.025)).toBe('-2.50 pts');
    expect(signedPoints(0)).toBe('0.00 pts');
  });

  it('rounds fractions to two-decimal percentage values for tables and CSV', () => {
    expect(percentValue(0.501931)).toBe(50.19);
    expect(percentValue(0.5)).toBe(50);
    expect(percentValue(null)).toBeNull();
  });
});
