import { http, HttpResponse } from 'msw';

import type { RecordsOut } from './api';

export const recordsFixture: RecordsOut = {
  as_of: '2026-09-27',
  highest_scores: [
    { rank: 1, shooter_id: 7, display_name: 'Ace, Amy', event_date: '2021-01-17', value: 50 },
    { rank: 1, shooter_id: 3, display_name: 'Bee, Bob', event_date: '2022-12-04', value: 50 },
    { rank: 3, shooter_id: 9, display_name: 'Cy, Cal', event_date: '2021-03-28', value: 49 },
  ],
  perfect_rounds: [
    { rank: 1, shooter_id: 7, display_name: 'Ace, Amy', event_date: '2021-01-17', value: 50 },
    { rank: 1, shooter_id: 3, display_name: 'Bee, Bob', event_date: '2022-12-04', value: 50 },
  ],
  biggest_adjusted: [
    { rank: 1, shooter_id: 7, display_name: 'Ace, Amy', event_date: '2026-06-07', value: 18 },
  ],
  biggest_jumps: [
    {
      rank: 1,
      shooter_id: 9,
      display_name: 'Cy, Cal',
      event_date: '2021-03-21',
      prev_event_date: '2021-03-14',
      from_score: 11,
      to_score: 41,
      value: 30,
    },
  ],
  most_events: [
    { rank: 1, shooter_id: 3, display_name: 'Bee, Bob', value: 285 },
    { rank: 2, shooter_id: 7, display_name: 'Ace, Amy', value: 267 },
  ],
  longest_streaks: [{ rank: 1, shooter_id: 3, display_name: 'Bee, Bob', value: 56 }],
  highest_ratings: [
    { rank: 1, shooter_id: 7, display_name: 'Ace, Amy', event_date: '2024-03-10', value: 47.256 },
  ],
  totals: {
    highest_scores: 3,
    perfect_rounds: 2,
    biggest_adjusted: 1,
    biggest_jumps: 1,
    most_events: 2,
    longest_streaks: 1,
    highest_ratings: 1,
  },
  tied_more: {
    highest_scores: 0,
    perfect_rounds: 0,
    biggest_adjusted: 0,
    biggest_jumps: 0,
    most_events: 0,
    longest_streaks: 0,
    highest_ratings: 0,
  },
};

export const handlers = [http.get('*/api/records', () => HttpResponse.json(recordsFixture))];
