import { describe, expect, it } from 'vitest';
import {
  conditionLabel,
  difficultyNote,
  expectationSentence,
  forecastSummary,
  formatDay,
  formatRange,
  formatScore,
} from './format';
import { FORECAST, NEXT_PREDICTIONS } from './mocks';

describe('prediction formatting', () => {
  it('formats calendar days without a timezone shift', () => {
    expect(formatDay('2026-10-04')).toBe('Sun, Oct 4');
  });

  it('rounds scores to whole targets within 0..50', () => {
    expect(formatScore(36.44)).toBe('36');
    expect(formatScore(38.6)).toBe('39');
    expect(formatScore(-2)).toBe('0');
    expect(formatScore(53)).toBe('50');
  });

  it('formats a likely range clipped to 0..50', () => {
    expect(formatRange(38.6, 4.2)).toBe('34–43');
    expect(formatRange(48, 4)).toBe('44–50');
    expect(formatRange(2, 4)).toBe('0–6');
  });

  it('phrases an expectation neutrally', () => {
    const [hadley] = NEXT_PREDICTIONS.shooters;
    expect(hadley && expectationSentence(hadley)).toBe(
      'Expected around 35 next Sunday, likely 31–39.',
    );
  });

  it('summarises the forecast window', () => {
    expect(forecastSummary(FORECAST)).toBe('54°F · gusts to 12 mph · 0.02 in rain · Rain');
    expect(forecastSummary({ ...FORECAST, precip_in: 0, condition: 'partly_cloudy' })).toBe(
      '54°F · gusts to 12 mph · dry · Partly cloudy',
    );
    expect(conditionLabel('hail')).toBe('hail');
  });

  it('explains the day difficulty and its source', () => {
    expect(difficultyNote(NEXT_PREDICTIONS)).toBe(
      'About 1.2 targets harder than a typical Sunday, going by the forecast.',
    );
    expect(difficultyNote({ ...NEXT_PREDICTIONS, difficulty: -0.8 })).toBe(
      'About 0.8 targets easier than a typical Sunday, going by the forecast.',
    );
    expect(difficultyNote({ ...NEXT_PREDICTIONS, difficulty: 0.02 })).toBe(
      'A typical Sunday for scores, going by the forecast.',
    );
    expect(
      difficultyNote({ ...NEXT_PREDICTIONS, difficulty_source: 'intercept', difficulty: 0.1 }),
    ).toBe('No usable forecast yet, so this assumes a typical Sunday.');
    expect(
      difficultyNote({ ...NEXT_PREDICTIONS, difficulty_source: 'prior', difficulty: null }),
    ).toBe('No weather model yet, so this assumes a typical Sunday.');
  });
});
