import { http, HttpResponse } from 'msw';
import type { Recap } from './api';

export const regularRecap: Recap = {
  event_date: '2026-09-27',
  kind: 'regular',
  label: null,
  target_total: 50,
  shooters: 23,
  head_count: 24,
  rounds: 27,
  podium: [
    { place: 1, tied: true, score: 49, names: ['Stanton Finnegan', 'Ethan Stockton'] },
    { place: 3, tied: false, score: 47, names: ['Sid Devlin'] },
  ],
  pbs: [{ display_name: 'Noel Kaplan', score: 45, previous: 43 }],
  insights: [
    'Scores up 3 Sundays straight for Alvin McGinnis: 33, 36, then 46.',
    'A friendly Sunday: scores ran about 3 targets over a typical Sunday for this crowd. The middle score was 40.',
  ],
  trophies: [{ display_name: 'Preston Abernathy', items: ['Events Attended - 50'] }],
  club_milestones: ['350,000 clays thrown'],
  first_timers: ['Pat Kim'],
  three_bird_new: null,
  three_bird_holders: null,
  top_score: null,
  link: 'https://sundayclays.claysmasher.com/l/events/2026-09-27',
};

export const specialRecap: Recap = {
  event_date: '2026-09-20',
  kind: 'special',
  label: '3-Bird Shoot',
  target_total: 60,
  shooters: 40,
  head_count: null,
  rounds: 40,
  podium: [],
  pbs: [],
  insights: [],
  trophies: [],
  club_milestones: [],
  first_timers: ['Pat Kim'],
  three_bird_new: 12,
  three_bird_holders: 58,
  top_score: 55,
  link: 'https://sundayclays.claysmasher.com/l/events/2026-09-20',
};

export const handlers = [
  http.get('*/api/admin/recap/:date', ({ params }) =>
    HttpResponse.json(params.date === '2026-09-20' ? specialRecap : regularRecap),
  ),
];
