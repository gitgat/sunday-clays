import { describe, expect, it } from 'vitest';
import {
  formatDate,
  formatMonth,
  formatNumber,
  formatPercent,
  formatPrecip,
  formatPressure,
  formatShortDate,
  formatSigned,
  formatTemp,
  formatWind,
  parseIsoDate,
} from './format';

describe('format', () => {
  it('formats pressure from hPa to inHg with 2 decimals', () => {
    expect(formatPressure(1013.25)).toBe('29.92 inHg');
    expect(formatPressure(1000)).toBe('29.53 inHg');
  });

  it('formats numbers, percents and signed deltas', () => {
    expect(formatNumber(7480)).toBe('7,480');
    expect(formatNumber(35.2549, 2)).toBe('35.25');
    expect(formatPercent(72.1081)).toBe('72.1%');
    expect(formatSigned(2)).toBe('+2.0');
    expect(formatSigned(-1.46)).toBe('−1.5');
    expect(formatSigned(0.04)).toBe('0.0');
    expect(formatSigned(-0.04)).toBe('0.0');
  });

  it('gives the same output on repeated calls, whatever digits or dates came in between', () => {
    const numbers = () => [
      formatNumber(1234.5678, 2),
      formatNumber(1234.5678),
      formatPercent(12.345),
      formatNumber(1234.5678, 2),
    ];
    const dates = () => [
      formatDate('2026-09-13'),
      formatShortDate('2026-09-13'),
      formatMonth('2026-09'),
    ];
    expect(numbers()).toEqual(['1,234.57', '1,235', '12.3%', '1,234.57']);
    expect(numbers()).toEqual(numbers());
    expect(dates()).toEqual(['Sep 13, 2026', 'Sep 13', 'Sep 2026']);
    expect(dates()).toEqual(dates());
  });

  it('formats weather units', () => {
    expect(formatTemp(54.6)).toBe('55°F');
    expect(formatWind(12.4)).toBe('12 mph');
    expect(formatPrecip(0.051)).toBe('0.05 in');
  });

  it('renders a dash for missing or non-finite values', () => {
    for (const fn of [
      formatNumber,
      formatPercent,
      formatSigned,
      formatTemp,
      formatWind,
      formatPrecip,
      formatPressure,
    ]) {
      expect(fn(null)).toBe('—');
      expect(fn(undefined)).toBe('—');
      expect(fn(Number.NaN)).toBe('—');
    }
  });

  it('formats ISO dates as local calendar dates (no UTC shift)', () => {
    expect(formatDate('2026-09-13')).toBe('Sep 13, 2026');
    expect(formatShortDate('2026-01-04')).toBe('Jan 4');
    expect(formatMonth('2025-03')).toBe('Mar 2025');
    expect(parseIsoDate('2026-09-13')?.getDate()).toBe(13);
  });

  it('rejects malformed or impossible dates', () => {
    expect(parseIsoDate('2026-02-30')).toBeNull();
    expect(parseIsoDate('13/09/2026')).toBeNull();
    expect(formatDate('garbage')).toBe('—');
    expect(formatDate(null)).toBe('—');
    expect(formatMonth(undefined)).toBe('—');
  });
});
