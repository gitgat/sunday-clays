import { http, HttpResponse } from 'msw';

import type { LeaderboardHistoryOut } from './api';

export const historyFixture: LeaderboardHistoryOut = {
  period: 'season',
  metric: 'season_points',
  frames: [
    {
      event_date: '2026-09-06',
      rows: [
        { shooter_id: 7, display_name: 'Ace, Amy', status: 'member', value: 11, rank: 1 },
        { shooter_id: 3, display_name: 'Bee, Bob', status: 'member', value: 9, rank: 2 },
      ],
    },
    {
      event_date: '2026-09-13',
      rows: [
        { shooter_id: 3, display_name: 'Bee, Bob', status: 'member', value: 20, rank: 1 },
        { shooter_id: 7, display_name: 'Ace, Amy', status: 'member', value: 18, rank: 2 },
      ],
    },
    {
      event_date: '2026-09-27',
      rows: [
        { shooter_id: 3, display_name: 'Bee, Bob', status: 'member', value: 29, rank: 1 },
        { shooter_id: 7, display_name: 'Ace, Amy', status: 'member', value: 29, rank: 1 },
      ],
    },
  ],
};

export const handlers = [
  http.get('*/api/leaderboards/history', () => HttpResponse.json(historyFixture)),
];
