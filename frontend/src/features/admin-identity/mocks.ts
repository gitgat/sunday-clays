import { http, HttpResponse } from 'msw';
import type { DuplicatePair, EventDetail, EventResult, Rule } from './api';

/** Plan 04 orders each pair (smaller name key, larger name key) and sorts the pairs; shooter ids are illustrative. */
export const duplicatePairs: DuplicatePair[] = [
  {
    a: {
      shooter_id: 150,
      name_key: 'preutt clay',
      display_name: 'Preutt, Clay',
      n_rounds: 1,
      first_event: '2024-09-01',
      last_event: '2024-09-01',
    },
    b: {
      shooter_id: 151,
      name_key: 'pruett clay',
      display_name: 'Pruett, Clay',
      n_rounds: 1,
      first_event: '2024-09-15',
      last_event: '2024-09-15',
    },
  },
  {
    a: {
      shooter_id: 141,
      name_key: 'hammond bennett',
      display_name: 'Hammond, Bennett',
      n_rounds: 1,
      first_event: '2024-11-03',
      last_event: '2024-11-03',
    },
    b: {
      shooter_id: 140,
      name_key: 'hamond bennett',
      display_name: 'Hamond, Bennett',
      n_rounds: 28,
      first_event: '2024-11-24',
      last_event: '2026-09-27',
    },
  },
];

/** Illustrative rules: an active station alias and a deactivated status override. */
export const rules: Rule[] = [
  {
    id: 1,
    rule_type: 'alias_name',
    payload: { name_key: 'hadley dik', shooter_id: 3 },
    active: true,
    note: 'Station typo',
    created_at: '2026-09-20T17:00:00Z',
    deactivated_at: null,
  },
  {
    id: 2,
    rule_type: 'set_status',
    payload: { shooter_id: 41, status: 'deceased' },
    active: false,
    note: null,
    created_at: '2026-09-21T17:00:00Z',
    deactivated_at: '2026-09-22T17:00:00Z',
  },
];

const unmodelled = {
  gauge_class: null,
  shooter_status: 'member',
  percentile: null,
  adjusted: null,
  expected: null,
  residual: null,
  mu_before: null,
  mu_after: null,
  rating_delta: null,
} as const;

/** 2026-09-13 (fixture scores); Nickerson's second round is illustrative, hence 14 rounds by 13 shooters. */
export const pickerEvent: EventDetail = {
  event_date: '2026-09-13',
  round_type: 'super_sporting',
  round_type_source: 'stations',
  head_count: 13,
  has_scores: true,
  has_stations: true,
  results_complete: true,
  n_rounds: 14,
  n_shooters: 13,
  median: 34,
  mean: 34.462,
  stdev: 4.807,
  top_score: 42,
  difficulty: 2.1,
  results: [
    {
      ...unmodelled,
      round_id: 7444,
      shooter_id: 12,
      display_name: 'Nordquist, Sherman',
      name_key: 'nordquist sherman',
      ordinal: 1,
      score: 42,
      is_best_round: true,
      event_rank: 1,
    },
    {
      ...unmodelled,
      round_id: 7450,
      shooter_id: 3,
      display_name: 'Hadley, Ike',
      name_key: 'hadley ike',
      ordinal: 1,
      score: 34,
      is_best_round: true,
      event_rank: 7,
    },
    {
      ...unmodelled,
      round_id: 7461,
      shooter_id: 20,
      display_name: 'Nickerson, Neal',
      name_key: 'nickerson neal',
      ordinal: 2,
      score: 34,
      is_best_round: false,
      event_rank: null,
    },
  ],
  weather: null,
  stations: null,
  notables: [],
  vs_prev: null,
};

export const pickerResults: EventResult[] = pickerEvent.results;

// Default handlers: branch-free, exercised by routes.test.tsx.
export const handlers = [
  http.get('*/api/admin/possible-duplicates', () => HttpResponse.json(duplicatePairs)),
  http.post('*/api/admin/shooters/merge', () =>
    HttpResponse.json({ shared_dates: 0, job_id: null }),
  ),
  http.post('*/api/admin/shooters/:id/rename', () => HttpResponse.json({ rule_id: 5, job_id: 61 })),
  http.post('*/api/admin/shooters/:id/status', () => HttpResponse.json({ rule_id: 6, job_id: 62 })),
  http.get('*/api/admin/rules', () => HttpResponse.json(rules)),
  http.post('*/api/admin/rules', () => HttpResponse.json({ rule_id: 3, job_id: 63 })),
  http.post('*/api/admin/rules/:id/deactivate', ({ params }) =>
    HttpResponse.json({ rule_id: Number(params.id), job_id: 64 }),
  ),
];
