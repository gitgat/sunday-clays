import { http, HttpResponse } from 'msw';
import type { ShooterSummary } from './api';

export const summaryFixture: ShooterSummary = {
  shooter_id: 3,
  display_name: 'Hadley, Ike',
  from: '2026-06-28',
  to: '2026-09-27',
  sundays: 11,
  special_sundays: 1,
  rounds: 12,
  average: 41.3,
  best: { score: 46, event_date: '2026-09-13' },
  pbs_set: 1,
  trophies: 3,
  trophy_names: ['Iron Streak — Bronze', 'Events Attended — Gold'],
  longest_streak: 6,
};

export const handlers = [
  http.get('*/api/shooters/:id/summary', () => HttpResponse.json(summaryFixture)),
];
