import { http, HttpResponse } from 'msw';
import type { Leaderboard, YirClub, YirShooter } from './api';

const CLUB_MONTHS: YirClub['months'] = [
  { month: 1, events: 4, rounds: 119, avg_score: 35.0924 },
  { month: 2, events: 4, rounds: 117, avg_score: 37.8889 },
  ...[3, 4, 5, 6, 7, 8, 9, 10, 11, 12].map((month) => ({
    month,
    events: 0,
    rounds: 0,
    avg_score: null,
  })),
];

/** A complete `YirClubOut` shaped like the fixture's 2025. */
export const YIR_2025: YirClub = {
  year: 2025,
  years: [2020, 2021, 2022, 2023, 2024, 2025, 2026],
  totals: {
    year: 2025,
    scored_events: 48,
    held_events: 48,
    rounds: 1267,
    shooters: 139,
    clays_thrown: 63350,
    clays_broken: 44683,
    avg_score: 35.2668,
  },
  events: 50,
  newcomers: 57,
  perfect_rounds: 1,
  top_rounds: [
    { shooter_id: 307, display_name: 'Grimsby, Gregor', event_date: '2025-08-03', score: 50 },
  ],
  mean_head_count: 25.92,
  busiest: { event_date: '2025-08-17', value: 40 },
  hardest: { event_date: '2025-11-16', value: 3.1 },
  easiest: { event_date: '2025-02-09', value: -2.4 },
  trophies: 612,
  months: CLUB_MONTHS,
  previous: {
    year: 2024,
    scored_events: 48,
    held_events: 47,
    rounds: 1193,
    shooters: 125,
    clays_thrown: 59650,
    clays_broken: 41088,
    avg_score: 34.4409,
  },
};

/** A complete `YirShooterOut` shaped like Grimsby, Gregor's 2025. */
export const YIR_GRIMSBY_2025: YirShooter = {
  year: 2025,
  shooter_id: 307,
  display_name: 'Grimsby, Gregor',
  totals: {
    year: 2025,
    events: 26,
    rounds: 27,
    clays_thrown: 1350,
    clays_broken: 1169,
    avg_score: 43.2963,
  },
  best: { shooter_id: 307, display_name: 'Grimsby, Gregor', event_date: '2025-08-03', score: 50 },
  wins: 7,
  podiums: 13,
  best_finish: 1,
  pbs: [
    { event_date: '2025-03-23', score: 49 },
    { event_date: '2025-08-03', score: 50 },
  ],
  trophies: 9,
  rating_start: 44.1,
  rating_end: 45.32,
  attendance_rank: 19,
  n_shooters: 139,
  months: [
    { month: 1, rounds: 2, avg_score: 44.5, club_avg_score: 35.0924 },
    ...[2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12].map((month) => ({
      month,
      rounds: 0,
      avg_score: null,
      club_avg_score: null,
    })),
  ],
  previous: {
    year: 2024,
    events: 23,
    rounds: 23,
    clays_thrown: 1150,
    clays_broken: 966,
    avg_score: 42,
  },
};

export const YEAR_BOARD: Leaderboard = {
  period: 'ytd',
  metric: 'events',
  as_of: '2025-12-31',
  start: '2025-01-01',
  end: '2025-12-31',
  min_rounds_applied: 1,
  n_eligible: 139,
  event_dates: ['2025-01-05'],
  rows: [
    {
      rank: 1,
      shooter_id: 59,
      display_name: 'Hadley, Ike',
      status: 'member',
      value: 44,
      n_rounds: 44,
    },
    {
      rank: 1,
      shooter_id: 194,
      display_name: 'Abernathy, Preston',
      status: 'member',
      value: 44,
      n_rounds: 45,
    },
    {
      rank: 3,
      shooter_id: 210,
      display_name: 'Kaplan, Noel',
      status: 'member',
      value: 43,
      n_rounds: 44,
    },
    {
      rank: 3,
      shooter_id: 255,
      display_name: 'Kolmanov, Dmitri',
      status: 'member',
      value: 43,
      n_rounds: 43,
    },
    {
      rank: 5,
      shooter_id: 3,
      display_name: 'Waldrop, Quentin',
      status: 'member',
      value: 42,
      n_rounds: 42,
    },
    {
      rank: 6,
      shooter_id: 8,
      display_name: 'Dodgson, Nick',
      status: 'member',
      value: 41,
      n_rounds: 41,
    },
  ],
};

/**
 * `GET /api/leaderboards` belongs to the leaderboards feature, so it is not a default handler here;
 * tests that render the leaders install this one with `server.use`.
 */
export const leaderboardHandler = http.get('*/api/leaderboards', () =>
  HttpResponse.json(YEAR_BOARD),
);

export const handlers = [
  http.get('*/api/yir/:year', () => HttpResponse.json(YIR_2025)),
  http.get('*/api/yir/:year/shooters/:id', () => HttpResponse.json(YIR_GRIMSBY_2025)),
];
