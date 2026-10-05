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
  insights: [
    'Scores up 3 Sundays straight for Alvin McGinnis: 33, 36, then 46.',
    'A friendly Sunday: scores ran about 3 targets over a typical Sunday for this crowd. The middle score was 40.',
  ],
  milestones: [
    'Wylie Marsden has now broken 4,000 targets on Sundays: 4,018 in all.',
    'Preston Abernathy: Clays Broken - 1,000',
    'Pat Kim: Clays Broken - 1,000',
    'Club: 7,500 rounds shot all time!',
  ],
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
  insights: [],
  milestones: ['Ike Hadley: Clays Broken - 500'],
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
