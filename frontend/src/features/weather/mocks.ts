import { http, HttpResponse } from 'msw';
import type { WeatherEffects, WeatherEvent, WeatherSensitivity, WeatherTurnout } from './api';

function event(overrides: Partial<WeatherEvent>): WeatherEvent {
  return {
    event_date: '2026-09-13',
    round_type: 'super_sporting',
    head_count: 13,
    has_scores: true,
    n_rounds: 13,
    median: 34,
    mean: 34.46,
    top_score: 42,
    difficulty: 1.2,
    temp_f: 60,
    apparent_f: 58,
    precip_in: 0.3,
    wind_mph: 12.5,
    gust_mph: 25,
    wind_dir_deg: 200,
    cloud_pct: 100,
    humidity_pct: 80,
    pressure_hpa: 1012,
    condition: 'rain',
    temp_band: '55-70',
    wind_band: '20+',
    precip_band: 'wet',
    ...overrides,
  };
}

export const WEATHER_EVENTS: WeatherEvent[] = [
  event({
    event_date: '2018-12-30',
    round_type: 'sporting',
    head_count: 7,
    has_scores: false,
    n_rounds: 0,
    median: null,
    mean: null,
    top_score: null,
    difficulty: null,
    temp_f: 35,
    precip_in: 0,
    gust_mph: 4,
    wind_dir_deg: 0,
    cloud_pct: 90,
    condition: 'overcast',
    temp_band: '<40',
    wind_band: '<10',
    precip_band: 'dry',
  }),
  event({
    event_date: '2026-08-16',
    round_type: 'sporting',
    head_count: 48,
    n_rounds: 48,
    median: 39,
    difficulty: -1.5,
    temp_f: 80,
    precip_in: 0,
    gust_mph: 12,
    wind_dir_deg: 270,
    cloud_pct: 10,
    condition: 'clear',
    temp_band: '70-85',
    wind_band: '10-20',
    precip_band: 'dry',
  }),
  event({}),
  event({
    event_date: '2026-09-27',
    round_type: 'sporting',
    head_count: 23,
    n_rounds: 23,
    median: 39,
    difficulty: -0.5,
    temp_f: 58,
    precip_in: 0,
    gust_mph: 6,
    wind_dir_deg: null,
    cloud_pct: 40,
    condition: 'partly_cloudy',
    precip_band: 'dry',
    wind_band: '<10',
  }),
];

export const WEATHER_EFFECTS: WeatherEffects = {
  model: {
    terms: [
      { name: 'intercept', coef: 1, se: 0.5, mean: null },
      { name: 'temp_f', coef: -0.02, se: 0.01, mean: 60 },
      { name: 'gust_mph', coef: 0.1, se: 0.03, mean: 12 },
      { name: 'precip_in', coef: 2, se: 1, mean: 0.05 },
      { name: 'cloud_pct', coef: 0.01, se: 0.005, mean: 50 },
    ],
    sigma2: 3.2,
    n_events: 84,
  },
  n_events: 4,
  bands: [
    {
      dimension: 'temp_band',
      band: '55-70',
      n_events: 2,
      n_rounds: 36,
      mean_score: 36.5,
      mean_difficulty: 0.35,
    },
    {
      dimension: 'temp_band',
      band: '70-85',
      n_events: 1,
      n_rounds: 48,
      mean_score: 37.354,
      mean_difficulty: -1.5,
    },
    {
      dimension: 'wind_band',
      band: '<10',
      n_events: 1,
      n_rounds: 23,
      mean_score: 39.13,
      mean_difficulty: -0.5,
    },
    {
      dimension: 'condition',
      band: 'rain',
      n_events: 1,
      n_rounds: 13,
      mean_score: 34.46,
      mean_difficulty: null,
    },
    {
      dimension: 'time_of_year',
      band: 'summer',
      n_events: 1,
      n_rounds: 48,
      mean_score: 37.354,
      mean_difficulty: -1.5,
    },
    {
      dimension: 'time_of_year',
      band: 'fall',
      n_events: 2,
      n_rounds: 36,
      mean_score: 36.5,
      mean_difficulty: 0.35,
    },
  ],
};

export const WEATHER_SENSITIVITY: WeatherSensitivity = {
  scales: [
    { covariate: 'temp_f', mean: 45.38, sd: 8.9 },
    { covariate: 'gust_mph', mean: 11.48, sd: 6.45 },
    { covariate: 'precip_in', mean: 0.052, sd: 0.05 },
  ],
  tau2: [
    { covariate: 'temp_f', tau2: 0.2 },
    { covariate: 'gust_mph', tau2: 0.3 },
    { covariate: 'precip_in', tau2: 0 },
  ],
  shooters: [
    {
      shooter_id: 59,
      display_name: 'Hadley, Ike',
      n_rounds: 78,
      terms: [
        { covariate: 'temp_f', beta: 0.3, se: 0.2, shrunk: 0.25, per_unit: 0.281 },
        { covariate: 'gust_mph', beta: -0.5, se: 0.3, shrunk: -0.4, per_unit: -0.62 },
        { covariate: 'precip_in', beta: null, se: null, shrunk: 0, per_unit: 0 },
      ],
    },
    {
      shooter_id: 194,
      display_name: 'Abernathy, Preston',
      n_rounds: 80,
      terms: [
        { covariate: 'temp_f', beta: -0.1, se: 0.2, shrunk: -0.05, per_unit: -0.056 },
        { covariate: 'gust_mph', beta: 0.2, se: 0.3, shrunk: 0.1, per_unit: 0.154 },
        { covariate: 'precip_in', beta: 0.1, se: 0.5, shrunk: 0, per_unit: 0 },
      ],
    },
  ],
};

export const WEATHER_TURNOUT: WeatherTurnout[] = [
  { dimension: 'temp_band', band: '<40', n_events: 1, mean_head_count: 7, median_head_count: 7 },
  {
    dimension: 'temp_band',
    band: '55-70',
    n_events: 2,
    mean_head_count: 18,
    median_head_count: 18,
  },
  { dimension: 'wind_band', band: '<10', n_events: 2, mean_head_count: 15, median_head_count: 15 },
  {
    dimension: 'time_of_year',
    band: 'winter',
    n_events: 1,
    mean_head_count: 7,
    median_head_count: 7,
  },
  {
    dimension: 'time_of_year',
    band: 'fall',
    n_events: 2,
    mean_head_count: 18,
    median_head_count: 18,
  },
];

export const handlers = [
  http.get('*/api/weather/events', () => HttpResponse.json(WEATHER_EVENTS)),
  http.get('*/api/weather/effects', () => HttpResponse.json(WEATHER_EFFECTS)),
  http.get('*/api/weather/sensitivity', () => HttpResponse.json(WEATHER_SENSITIVITY)),
  http.get('*/api/weather/turnout', () => HttpResponse.json(WEATHER_TURNOUT)),
];
