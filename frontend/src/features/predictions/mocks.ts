import { http, HttpResponse } from 'msw';
import type { NextPredictions, PredictionForecast } from './api';

export const FORECAST: PredictionForecast = {
  fetched_at: '2026-09-30T13:00:00Z',
  temp_f: 54.2,
  apparent_f: 52.0,
  precip_in: 0.02,
  wind_mph: 6.1,
  gust_mph: 12.4,
  cloud_pct: 80,
  condition: 'rain',
};

/** A complete `NextPredictionsOut` (every field) for Vitest + MSW. Expected scores only. */
export const NEXT_PREDICTIONS: NextPredictions = {
  target_date: '2026-10-04',
  model_ready: true,
  forecast: FORECAST,
  difficulty: 1.24,
  difficulty_sd: 2.1,
  difficulty_source: 'weather',
  field_median: 36.44,
  expected_turnout: 27.15,
  shooters: [
    { shooter_id: 59, display_name: 'Hadley, Ike', attend_prob: 1, expected: 35.2, sd: 4.1 },
    {
      shooter_id: 121,
      display_name: 'Finnegan, Stanton',
      attend_prob: 4 / 13,
      expected: 41.3,
      sd: 4.6,
    },
    {
      shooter_id: 194,
      display_name: 'Abernathy, Preston',
      attend_prob: 1,
      expected: 38.6,
      sd: 4.2,
    },
  ],
};

export const handlers = [
  http.get('*/api/predictions/next', () => HttpResponse.json(NEXT_PREDICTIONS)),
];
