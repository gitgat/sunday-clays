import { http, HttpResponse } from 'msw';
import type { AuditEntry, BumpedPost, DataIssue } from './api';

export const dataIssues: DataIssue[] = [
  {
    id: 1,
    code: 'incomplete_results',
    severity: 'warning',
    event_date: '2024-11-10',
    shooter_id: null,
    message: '7 shooters recorded vs a head count of 27',
    details: { n_shooters: 7, head_count: 27 },
  },
  {
    id: 2,
    code: 'station_score_mismatch',
    severity: 'warning',
    event_date: '2026-09-13',
    shooter_id: 3,
    message: 'Station total 36 vs score 34',
    details: { station_total: 36, score: 34 },
  },
  {
    id: 3,
    code: 'station_name_unmatched',
    severity: 'warning',
    event_date: '2026-09-13',
    shooter_id: null,
    message: 'No shooter matches “Hadley, Dik”',
    details: { name_key: 'hadley dik', raw_name: 'Hadley, Dik', event_date: '2026-09-13' },
  },
  {
    id: 4,
    code: 'merged_same_day_rounds',
    severity: 'info',
    event_date: '2026-08-30',
    shooter_id: 20,
    message: 'Two names of one shooter shot the same day',
    details: {},
  },
];

/** Oldest first on purpose: the server sends newest first, and the table sorts by id itself. */
export const auditEntries: AuditEntry[] = [
  {
    id: 1,
    at: '2026-09-27T18:05:20Z',
    ip: '203.0.113.7',
    role: 'admin',
    action: 'imports.commit',
    details: { import_id: 1, confirm_removals: false, job_id: 11 },
  },
  {
    id: 2,
    at: '2026-09-27T18:06:30Z',
    ip: null,
    role: 'admin',
    action: 'rules.create',
    details: {
      rule_id: 1,
      rule_type: 'alias_name',
      payload: { name_key: 'hadley dik', shooter_id: 3 },
      job_id: 12,
    },
  },
];

export const bumpedPosts: BumpedPost[] = [
  {
    post_key: 'k-pb-3',
    bumps: 4,
    last_at: '2026-09-28T09:15:00Z',
    label: 'New personal best for Ike Hadley: 46.',
    issue_date: '2026-09-27',
    current: true,
  },
  {
    post_key: 'trophy:retired_trophy:2026-09-13',
    bumps: 1,
    last_at: '2026-09-14T20:00:00Z',
    label: 'Trophy retired_trophy, 2026-09-13',
    issue_date: '2026-09-13',
    current: false,
  },
];

// Default handlers: branch-free, exercised by routes.test.tsx.
export const handlers = [
  http.get('*/api/admin/data-issues', () => HttpResponse.json(dataIssues)),
  http.get('*/api/admin/audit', () => HttpResponse.json(auditEntries)),
  http.post('*/api/admin/recompute', () => HttpResponse.json({ job_id: 81 })),
  http.post('*/api/admin/shooters/:id/aliases', () =>
    HttpResponse.json({ rule_id: 4, job_id: 82 }),
  ),
  http.get('*/api/admin/sheet/bumps', () => HttpResponse.json(bumpedPosts)),
  http.delete('*/api/admin/sheet/bumps/:postKey', ({ params }) =>
    HttpResponse.json({ post_key: String(params['postKey']), wiped: 4 }),
  ),
];
