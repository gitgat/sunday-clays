import type { NextPredictions, PredictionForecast, PredictedShooter } from './api';

const DAY = new Intl.DateTimeFormat('en-US', {
  weekday: 'short',
  month: 'short',
  day: 'numeric',
  timeZone: 'UTC',
});

/** "2026-10-04" -> "Sun, Oct 4" (calendar dates carry no timezone). */
export function formatDay(iso: string): string {
  return DAY.format(new Date(`${iso}T00:00:00Z`));
}

/** Scores are whole targets, so predictions are shown as whole targets. */
export function formatScore(value: number): string {
  return String(Math.round(Math.min(50, Math.max(0, value))));
}

/** The likely range: expected plus or minus one standard deviation, clipped to 0..50. */
export function formatRange(expected: number, sd: number): string {
  return `${formatScore(expected - sd)}–${formatScore(expected + sd)}`;
}

/** "Expected around 39 next Sunday, likely 34–43." */
export function expectationSentence(s: PredictedShooter): string {
  return `Expected around ${formatScore(s.expected)} next Sunday, likely ${formatRange(s.expected, s.sd)}.`;
}

const CONDITIONS: Record<string, string> = {
  rain: 'Rain',
  windy: 'Windy',
  overcast: 'Overcast',
  partly_cloudy: 'Partly cloudy',
  clear: 'Clear',
};

export function conditionLabel(condition: string): string {
  return CONDITIONS[condition] ?? condition;
}

/** "54°F · gusts to 12 mph · 0.02 in rain · Rain" for the 10:00–12:00 window. */
export function forecastSummary(forecast: PredictionForecast): string {
  const parts = [
    `${Math.round(forecast.temp_f)}°F`,
    `gusts to ${Math.round(forecast.gust_mph)} mph`,
    forecast.precip_in > 0 ? `${forecast.precip_in.toFixed(2)} in rain` : 'dry',
    conditionLabel(forecast.condition),
  ];
  return parts.join(' · ');
}

/** Plain-Quigley day difficulty (positive = harder) and where it came from. */
export function difficultyNote(p: NextPredictions): string {
  if (p.difficulty_source === 'weather' && p.difficulty !== null) {
    const size = Math.abs(p.difficulty);
    if (size < 0.05) return 'A typical Sunday for scores, going by the forecast.';
    const way = p.difficulty > 0 ? 'harder' : 'easier';
    return `About ${size.toFixed(1)} targets ${way} than a typical Sunday, going by the forecast.`;
  }
  if (p.difficulty_source === 'intercept') {
    return 'No usable forecast yet, so this assumes a typical Sunday.';
  }
  return 'No weather model yet, so this assumes a typical Sunday.';
}
