import { http, HttpResponse } from 'msw';

import type { LeaderboardOut, MoversOut } from './api';

export const leaderboardFixture: LeaderboardOut = {
  period: 'season',
  metric: 'avg_score',
  as_of: '2026-09-27',
  min_rounds_applied: 5,
  n_eligible: 3,
  event_dates: ['2026-09-06', '2026-09-13', '2026-09-27'],
  start: '2026-08-03',
  end: '2026-09-27',
  rows: [
    {
      rank: 1,
      shooter_id: 7,
      display_name: 'Ace, Amy',
      status: 'member',
      value: 45.02,
      n_rounds: 12,
    },
    {
      rank: 2,
      shooter_id: 3,
      display_name: 'Bee, Bob',
      status: 'member',
      value: 44.5,
      n_rounds: 20,
    },
    { rank: 2, shooter_id: 9, display_name: 'Cy, Cal', status: 'guest', value: 44.5, n_rounds: 9 },
  ],
};

export const moversFixture: MoversOut = {
  period: 'season',
  as_of: '2026-09-27',
  start: '2026-08-03',
  end: '2026-09-27',
  rows: [
    { shooter_id: 9, display_name: 'Cy, Cal', gain: 3.4, n_rounds: 9 },
    { shooter_id: 3, display_name: 'Bee, Bob', gain: 1.2, n_rounds: 14 },
  ],
};

export const handlers = [
  // Echoes `since` and `as_of` like the API does, so a custom or earlier board reads as one.
  http.get('*/api/leaderboards', ({ request }) => {
    const params = new URL(request.url).searchParams;
    const since = params.get('since');
    const asOf = params.get('as_of');
    return HttpResponse.json({
      ...leaderboardFixture,
      since,
      start: since ?? leaderboardFixture.start,
      end: asOf ?? leaderboardFixture.end,
      as_of: asOf ?? leaderboardFixture.as_of,
    });
  }),
  http.get('*/api/leaderboards/movers', () => HttpResponse.json(moversFixture)),
];
