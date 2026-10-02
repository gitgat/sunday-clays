import { http, HttpResponse } from 'msw';
import type {
  AttendancePoint,
  ClubSummary,
  ClubTrends,
  Cohort,
  FirstRounds,
  ConversionYear,
  DistributionGroup,
  ParityYear,
  Regulars,
} from './api';

export const clubSummary: ClubSummary = {
  first_event: '2020-01-05',
  last_event: '2026-09-27',
  n_events: 360,
  n_scored_events: 311,
  n_held_events: 310,
  n_rounds: 7480,
  n_shooters: 332,
  avg_score: 34.955,
  median_score: 36,
  top_score: 50,
  n_perfect: 6,
  clays_thrown: 374000,
  clays_broken: 261461,
  avg_head_count: 22.558,
  shooters_by_status: { member: 214, guest: 109, deceased: 9 },
  status_by_year: [
    {
      year: 2025,
      member_rounds: 1210,
      guest_rounds: 45,
      deceased_rounds: 12,
      unrecorded_rounds: 0,
    },
    { year: 2026, member_rounds: 915, guest_rounds: 54, deceased_rounds: 0, unrecorded_rounds: 0 },
  ],
};

/** Two attendance-only dates, a multi-round day (36 score rows by 35 shooters) and two ordinary days. */
export const clubAttendance: AttendancePoint[] = [
  {
    kind: 'regular',
    label: null,
    target_total: 50,
    event_date: '2018-12-30',
    head_count: 7,
    n_rounds: 0,
    n_shooters: 0,
    has_scores: false,
    results_complete: false,
  },
  {
    kind: 'regular',
    label: null,
    target_total: 50,
    event_date: '2019-01-14',
    head_count: 9,
    n_rounds: 0,
    n_shooters: 0,
    has_scores: false,
    results_complete: false,
  },
  {
    kind: 'regular',
    label: null,
    target_total: 50,
    event_date: '2026-08-30',
    head_count: 36,
    n_rounds: 36,
    n_shooters: 35,
    has_scores: true,
    results_complete: true,
  },
  {
    kind: 'regular',
    label: null,
    target_total: 50,
    event_date: '2026-09-13',
    head_count: 13,
    n_rounds: 13,
    n_shooters: 13,
    has_scores: true,
    results_complete: true,
  },
  {
    kind: 'regular',
    label: null,
    target_total: 50,
    event_date: '2026-09-27',
    head_count: 23,
    n_rounds: 23,
    n_shooters: 23,
    has_scores: true,
    results_complete: true,
  },
];

/** 20 first rounds: 22 ×2, 30 ×5, 34 ×8, 38 ×4, 45 ×1. */
export const clubFirstRounds: FirstRounds = {
  n: 20,
  median: 34,
  counts: Array.from({ length: 51 }, (_, score) =>
    score === 22
      ? 2
      : score === 30
        ? 5
        : score === 34
          ? 8
          : score === 38
            ? 4
            : score === 45
              ? 1
              : 0,
  ),
};

export const clubCohorts: Cohort[] = [
  {
    year: 2024,
    n_new: 35,
    n_returned: 18,
    retention: [
      { offset: 0, n_active: 35, share: 1 },
      { offset: 1, n_active: 14, share: 0.4 },
      { offset: 2, n_active: 9, share: 0.2571 },
    ],
  },
  {
    year: 2025,
    n_new: 57,
    n_returned: 24,
    retention: [
      { offset: 0, n_active: 57, share: 1 },
      { offset: 1, n_active: 20, share: 0.3509 },
    ],
  },
  { year: 2026, n_new: 41, n_returned: 15, retention: [{ offset: 0, n_active: 41, share: 1 }] },
];

function counts(entries: Record<number, number>): number[] {
  return Array.from({ length: 51 }, (_, score) => entries[score] ?? 0);
}

/** Two tiny years; mean and numpy-linear quantiles hand-checked from the counts. */
export const clubDistribution: DistributionGroup[] = [
  {
    key: '2025',
    n: 4,
    mean: 40.75,
    median: 40.5,
    p10: 40,
    p25: 40,
    p75: 41.25,
    p90: 41.7,
    counts: counts({ 40: 2, 41: 1, 42: 1 }),
  },
  {
    key: '2026',
    n: 2,
    mean: 45.5,
    median: 45.5,
    p10: 41.9,
    p25: 43.25,
    p75: 47.75,
    p90: 49.1,
    counts: counts({ 41: 1, 50: 1 }),
  },
];

/** Shooter ids are illustrative. */
export const clubRegulars: Regulars = {
  as_of: '2026-09-27',
  n_held_window: 48,
  core: [
    { shooter_id: 7, display_name: 'Abernathy, Preston', events_attended: 46, share: 0.9583 },
    { shooter_id: 3, display_name: 'Hadley, Ike', events_attended: 42, share: 0.875 },
  ],
  lapsed: [{ shooter_id: 58, display_name: 'Nesbitt, Rolf', last_event: '2026-05-31' }],
};

export const clubConversion: ConversionYear[] = [
  { year: 2024, new_guests: 11, converted: 1, median_days_to_convert: 112 },
  { year: 2025, new_guests: 31, converted: 2, median_days_to_convert: 224 },
  { year: 2026, new_guests: 29, converted: 1, median_days_to_convert: 217 },
];

/** favorite_win_rate is illustrative (it needs the skill model's mu_before). */
export const clubParity: ParityYear[] = [
  { year: 2025, n_events: 48, distinct_winners: 23, top3_share: 0.3898, favorite_win_rate: 0.146 },
  { year: 2026, n_events: 36, distinct_winners: 18, top3_share: 0.3864, favorite_win_rate: 0.111 },
];

/** Difficulties are illustrative; the server always sends twelve months (three shown). */
export const clubTrends: ClubTrends = {
  as_of: '2026-09-27',
  years: [
    {
      year: 2020,
      events_held: 39,
      mean_head_count: 20.7,
      unique_shooters: 92,
      ytd_events: 26,
      ytd_rounds: 542,
      ytd_unique_shooters: 78,
      ytd_events_yoy: null,
    },
    {
      year: 2025,
      events_held: 48,
      mean_head_count: 25.92,
      unique_shooters: 139,
      ytd_events: 35,
      ytd_rounds: 945,
      ytd_unique_shooters: 127,
      ytd_events_yoy: 0.0294,
    },
    {
      year: 2026,
      events_held: 36,
      mean_head_count: 26.9167,
      unique_shooters: 129,
      ytd_events: 36,
      ytd_rounds: 969,
      ytd_unique_shooters: 129,
      ytd_events_yoy: 0.0286,
    },
  ],
  events: [
    {
      event_date: '2026-09-06',
      top_score: 48,
      median: 36,
      difficulty: 0.3,
      top_score_rolling8: 46.875,
      median_rolling8: 38.125,
      difficulty_rolling8: 0.44,
    },
    {
      event_date: '2026-09-13',
      top_score: 42,
      median: 34,
      difficulty: 2.1,
      top_score_rolling8: 46.5,
      median_rolling8: 37.375,
      difficulty_rolling8: 0.61,
    },
    {
      event_date: '2026-09-27',
      top_score: 49,
      median: 39,
      difficulty: -1.4,
      top_score_rolling8: 46.625,
      median_rolling8: 37.25,
      difficulty_rolling8: 0.33,
    },
  ],
  months: [
    { month: 1, n_events: 28, mean_head_count: 23.4643, mean_median: 36.2857 },
    { month: 9, n_events: 27, mean_head_count: 21.963, mean_median: 35.9259 },
    { month: 12, n_events: 24, mean_head_count: 21.375, mean_median: 35.5208 },
  ],
};

// Default handlers are branch-free (every line runs in routes.test.tsx); tests needing other data use server.use.
export const handlers = [
  http.get('*/api/club/summary', () => HttpResponse.json(clubSummary)),
  http.get('*/api/club/attendance', () => HttpResponse.json(clubAttendance)),
  http.get('*/api/club/cohorts', () => HttpResponse.json(clubCohorts)),
  http.get('*/api/club/first-rounds', () => HttpResponse.json(clubFirstRounds)),
  http.get('*/api/club/distribution', () => HttpResponse.json(clubDistribution)),
  http.get('*/api/club/regulars', () => HttpResponse.json(clubRegulars)),
  http.get('*/api/club/conversion', () => HttpResponse.json(clubConversion)),
  http.get('*/api/club/parity', () => HttpResponse.json(clubParity)),
  http.get('*/api/club/trends', () => HttpResponse.json(clubTrends)),
];
