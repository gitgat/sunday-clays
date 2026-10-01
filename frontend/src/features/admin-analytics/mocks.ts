import { http, HttpResponse } from 'msw';
import type { BumpsSummary, PageKindViews, Uptake, Visitors } from './api';

export const visitors: Visitors = {
  days: [
    { day: '2026-09-27', devices: 14 },
    { day: '2026-09-28', devices: 3 },
    { day: '2026-09-29', devices: 2 },
    { day: '2026-09-30', devices: 4 },
    { day: '2026-10-01', devices: 1 },
  ],
  weeks: [
    { week: '2026-09-21', devices: 18 },
    { week: '2026-09-28', devices: 7 },
  ],
  busiest: [
    { day: '2026-09-27', devices: 14 },
    { day: '2026-09-30', devices: 4 },
    { day: '2026-09-28', devices: 3 },
  ],
};

export const pageKinds: PageKindViews[] = [
  { page_kind: 'home', views: 40 },
  { page_kind: 'profile', views: 22 },
  { page_kind: 'event', views: 9 },
  { page_kind: 'leaderboards', views: 5 },
];

export const bumps: BumpsSummary = {
  days: [
    { day: '2026-09-27', bumps: 5 },
    { day: '2026-09-28', bumps: 2 },
  ],
  top: [
    { key: 'a1b2c3d4e5f6a7b8c9d0', headline: 'Ike Hadley broke 45 for the first time', bumps: 6 },
    { key: 'ffffeeeeddddccccbbbb', headline: null, bumps: 1 },
  ],
  devices: 8,
  devices_all_time: 12,
};

export const uptake: Uptake = {
  weeks: [
    { week: '2026-09-21', picked: 9, skipped: 2, none: 7 },
    { week: '2026-09-28', picked: 4, skipped: 1, none: 2 },
  ],
  latest: { picked: 11, skipped: 3, none: 8 },
  latest_since: '2026-07-03',
};

export const handlers = [
  http.get('*/api/admin/analytics/visitors', () => HttpResponse.json(visitors)),
  http.get('*/api/admin/analytics/pages', () => HttpResponse.json(pageKinds)),
  http.get('*/api/admin/analytics/bumps', () => HttpResponse.json(bumps)),
  http.get('*/api/admin/analytics/me-states', () => HttpResponse.json(uptake)),
];
