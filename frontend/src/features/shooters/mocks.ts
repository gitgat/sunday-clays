import { http, HttpResponse } from 'msw';
import type {
  ClubDistributionGroup,
  Rating,
  ShooterDetail,
  ShooterInsights,
  ShooterListItem,
  ShooterRound,
  SpecialRound,
  SplitRow,
} from './api';

export const shooterList: ShooterListItem[] = [
  {
    shooter_id: 41,
    display_name: 'Gilchrist, Melvin',
    status: 'deceased',
    n_rounds: 11,
    n_events: 11,
    first_event: '2020-01-12',
    last_event: '2020-10-18',
    active: false,
    mu: 36.2,
  },
  {
    shooter_id: 3,
    display_name: 'Hadley, Ike',
    status: 'member',
    n_rounds: 267,
    n_events: 267,
    first_event: '2020-01-05',
    last_event: '2026-09-27',
    active: true,
    mu: 35.1,
  },
  {
    shooter_id: 7,
    display_name: 'Abernathy, Preston',
    status: 'member',
    n_rounds: 286,
    n_events: 285,
    first_event: '2020-01-05',
    last_event: '2026-09-27',
    active: true,
    mu: 38.4,
  },
  {
    shooter_id: 88,
    display_name: 'Mortlock, Beatrice',
    status: 'guest',
    n_rounds: 3,
    n_events: 3,
    first_event: '2026-02-01',
    last_event: '2026-09-06',
    active: false,
    mu: 33.9,
  },
];

export const hadleyDetail: ShooterDetail = {
  shooter_id: 3,
  display_name: 'Hadley, Ike',
  status: 'member',
  deceased: false,
  first_event: '2020-01-05',
  last_event: '2026-09-27',
  left_censored: true,
  current_mu: 35.1,
  current_var: 3.9,
  stats: {
    n_rounds: 267,
    n_events: 267,
    avg_score: 35.31,
    median_score: 36,
    best_score: 45,
    avg_adjusted: -0.45,
    wins: 2,
    podiums: 14,
    avg_percentile: 0.487,
  },
  odometer: {
    clays_thrown: 13350,
    clays_broken: 9427,
    hit_pct: 0.706,
    rounds: 267,
    events: 267,
    years_active: 7,
    current_streak: 2,
    longest_streak: 31,
    favorite_month: 6,
    trophies: 0,
  },
  pbs: [
    { scope: 'overall', key: 'all', score: 45, event_date: '2022-04-03', round_id: 3850 },
    { scope: 'year', key: '2025', score: 44, event_date: '2025-02-09', round_id: 6412 },
    { scope: 'year', key: '2026', score: 44, event_date: '2026-02-01', round_id: 6905 },
  ],
};

export const gilchristDetail: ShooterDetail = {
  shooter_id: 41,
  display_name: 'Gilchrist, Melvin',
  status: 'deceased',
  deceased: true,
  first_event: '2020-01-12',
  last_event: '2020-10-18',
  left_censored: true,
  current_mu: 36.2,
  current_var: 9.5,
  stats: {
    n_rounds: 11,
    n_events: 11,
    avg_score: 37.18,
    median_score: 37,
    best_score: 41,
    avg_adjusted: 2.46,
    wins: 0,
    podiums: 4,
    avg_percentile: 0.687,
  },
  odometer: {
    clays_thrown: 550,
    clays_broken: 409,
    hit_pct: 0.744,
    rounds: 11,
    events: 11,
    years_active: 1,
    current_streak: 0,
    longest_streak: 6,
    favorite_month: 9,
    trophies: 0,
  },
  pbs: [
    { scope: 'overall', key: 'all', score: 41, event_date: '2020-09-20', round_id: 610 },
    { scope: 'year', key: '2020', score: 41, event_date: '2020-09-20', round_id: 610 },
  ],
};

/** Hadley has passed every C12 `events` tier (250), so the next milestone is null. */
export const hadleyInsights: ShooterInsights = {
  shooter_id: 3,
  as_of: '2026-09-27',
  n_rounds: 267,
  floor: 30.9,
  ceiling: 40,
  recent_n: 20,
  bad_day_rate: 0.183,
  form: 3.4,
  form_label: 'hot',
  wins: 2,
  podiums: 14,
  avg_percentile: 0.487,
  peak_mu: 38.2,
  peak_date: '2023-06-11',
  learning_curve: [
    { k: 1, value: -4, club_median: -3, n_club: 180 },
    { k: 2, value: -2.5, club_median: -2, n_club: 164 },
    { k: 3, value: -1, club_median: -1.5, n_club: 151 },
  ],
  rust: { effect: -2.1, n: 4, club_effect: -1.3 },
  milestone: { next_events: null, events_to_go: null, weekly_rate: 0.81, projected_date: null },
};

const unrated = {
  expected: null,
  residual: null,
  gauge_class: null,
  status: 'member',
  round_type: 'sporting',
  condition: null,
} as const;

/** Plan 17: Hadley's one special shoot (invented name). */
export const hadleySpecials: SpecialRound[] = [
  { round_id: 9001, event_date: '2026-09-20', label: '3-Bird Shoot', target_total: 60, score: 55 },
];

/** Hadley's last six rounds (fixture scores and field medians; ranks/ratings illustrative). */
export const hadleyRounds: ShooterRound[] = [
  {
    ...unrated,
    round_id: 7300,
    event_date: '2026-08-16',
    ordinal: 1,
    score: 39,
    field_median: 37,
    adjusted: 2,
    event_rank: 8,
    is_best_round: true,
    percentile: 0.62,
    mu_before: 35.1,
    mu_after: 35.3,
  },
  {
    ...unrated,
    round_id: 7350,
    event_date: '2026-08-23',
    ordinal: 1,
    score: 39,
    field_median: 36,
    adjusted: 3,
    event_rank: 7,
    is_best_round: true,
    percentile: 0.7,
    mu_before: 35.3,
    mu_after: 35.6,
  },
  {
    ...unrated,
    round_id: 7390,
    event_date: '2026-08-30',
    ordinal: 1,
    score: 36,
    field_median: 40.5,
    adjusted: -4.5,
    event_rank: 22,
    is_best_round: true,
    percentile: 0.3,
    mu_before: 35.6,
    mu_after: 35.4,
  },
  {
    ...unrated,
    round_id: 7438,
    event_date: '2026-09-06',
    ordinal: 1,
    score: 33,
    field_median: 36,
    adjusted: -3,
    event_rank: 19,
    is_best_round: true,
    percentile: 0.22,
    round_type: 'super_sporting',
    mu_before: 35.4,
    mu_after: 35.3,
  },
  {
    ...unrated,
    round_id: 7450,
    event_date: '2026-09-13',
    ordinal: 1,
    score: 34,
    field_median: 34,
    adjusted: 0,
    event_rank: 7,
    is_best_round: true,
    percentile: 0.5,
    round_type: 'super_sporting',
    mu_before: 35.3,
    mu_after: 35.0,
  },
  {
    ...unrated,
    round_id: 7471,
    event_date: '2026-09-27',
    ordinal: 1,
    score: 37,
    field_median: 39,
    adjusted: -2,
    event_rank: 16,
    is_best_round: true,
    percentile: 0.32,
    mu_before: 35.0,
    mu_after: 35.1,
  },
];

/** RatingOut: lo/hi = mu ∓ 1.96·√var (C7), rounded to 2 dp. */
export const hadleyRating: Rating = {
  shooter_id: 3,
  points: [
    { event_date: '2026-08-16', mu: 35.3, var: 4, lo: 31.38, hi: 39.22 },
    { event_date: '2026-08-23', mu: 35.6, var: 4, lo: 31.68, hi: 39.52 },
    { event_date: '2026-08-30', mu: 35.4, var: 4, lo: 31.48, hi: 39.32 },
    { event_date: '2026-09-06', mu: 35.3, var: 4, lo: 31.38, hi: 39.22 },
    { event_date: '2026-09-13', mu: 35.0, var: 4, lo: 31.08, hi: 38.92 },
    { event_date: '2026-09-27', mu: 35.1, var: 3.9, lo: 31.23, hi: 38.97 },
  ],
  current_mu: 35.1,
  peak_mu: 35.6,
  peak_date: '2026-08-23',
};

export const hadleySplitsByYear: SplitRow[] = [
  { key: '2025', n_rounds: 44, n_events: 44, avg: 35.9, median: 36, best: 44, avg_adjusted: -0.8 },
  {
    key: '2026',
    n_rounds: 33,
    n_events: 33,
    avg: 35.14,
    median: 35.5,
    best: 44,
    avg_adjusted: -1.1,
  },
];

export const hadleySplitsByGauge: SplitRow[] = [
  {
    key: 'unspecified',
    n_rounds: 267,
    n_events: 267,
    avg: 35.31,
    median: 36,
    best: 45,
    avg_adjusted: -0.45,
  },
];

function counts(entries: Record<number, number>): number[] {
  return Array.from({ length: 51 }, (_, score) => entries[score] ?? 0);
}

/** Two small years; quantiles are numpy-linear over the counted scores (hand-checked). */
export const clubDistribution: ClubDistributionGroup[] = [
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

// Default handlers are branch-free (every line runs in routes.test.tsx); tests needing other data use server.use.
export const handlers = [
  http.get('*/api/shooters', () => HttpResponse.json(shooterList)),
  http.get('*/api/shooters/:id', ({ params }) =>
    HttpResponse.json({ ...hadleyDetail, shooter_id: Number(params.id) }),
  ),
  http.get('*/api/shooters/:id/insights', ({ params }) =>
    HttpResponse.json({ ...hadleyInsights, shooter_id: Number(params.id) }),
  ),
  http.get('*/api/shooters/:id/rounds', () => HttpResponse.json(hadleyRounds)),
  http.get('*/api/shooters/:id/special', () => HttpResponse.json([])),
  http.get('*/api/shooters/:id/rating', () => HttpResponse.json(hadleyRating)),
  http.get('*/api/shooters/:id/splits', () => HttpResponse.json(hadleySplitsByYear)),
];
