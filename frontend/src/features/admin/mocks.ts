import { http, HttpResponse } from 'msw';
import type { ImportPreview, SpecialDiff, ImportSummary, Job, ShooterMatch } from './api';

export const importsList: ImportSummary[] = [
  {
    id: 1,
    kind: 'scores',
    filename: 'scores_2026-09-27.xlsx',
    status: 'committed',
    uploaded_at: '2026-09-27T18:05:00Z',
    committed_at: '2026-09-27T18:05:20Z',
    rolled_back_at: null,
    sha256: 'a'.repeat(64),
  },
  {
    id: 2,
    kind: 'stations',
    filename: 'stations_2026-09-27.xlsx',
    status: 'committed',
    uploaded_at: '2026-09-27T18:06:00Z',
    committed_at: '2026-09-27T18:06:30Z',
    rolled_back_at: null,
    sha256: 'b'.repeat(64),
  },
  {
    id: 3,
    kind: 'scores',
    filename: 'scores_old.xlsx',
    status: 'pending',
    uploaded_at: '2026-09-27T19:00:00Z',
    committed_at: null,
    rolled_back_at: null,
    sha256: 'c'.repeat(64),
  },
];

/** A stale scores file: two live events missing, one ERROR row, a station mismatch, warnings and info. */
export const stalePreview: ImportPreview = {
  import_id: 3,
  kind: 'scores',
  filename: 'scores_old.xlsx',
  duplicate_of: null,
  findings: [
    {
      code: 'score_missing',
      severity: 'error',
      message: 'Score Shot is blank',
      sheet: 'ALL SCORE DETAIL',
      row: 88,
      event_date: '2021-03-07',
      name: 'Eastwood, Stanley',
    },
    {
      code: 'station_score_mismatch',
      severity: 'warning',
      message: 'Station total 36 vs score 34',
      sheet: null,
      row: null,
      event_date: '2026-09-13',
      name: 'Hadley, Ike',
    },
    {
      code: 'non_sunday_date',
      severity: 'warning',
      message: '2019-01-14 is a Monday, not a Sunday (in Attendance History)',
      sheet: null,
      row: null,
      event_date: '2019-01-14',
      name: null,
    },
    {
      code: 'non_sunday_date',
      severity: 'warning',
      message: '2019-02-01 is a Friday, not a Sunday (in Attendance History)',
      sheet: null,
      row: null,
      event_date: '2019-02-01',
      name: null,
    },
    {
      code: 'attendance_without_scores',
      severity: 'info',
      message: 'Head count but no scores',
      sheet: 'Attendance History',
      row: 2,
      event_date: '2018-12-30',
      name: null,
    },
  ],
  diff: {
    events_added: [],
    events_removed: ['2026-09-13', '2026-09-27'],
    rows_added: 0,
    rows_removed: 36,
    rows_changed: 0,
    new_names: [],
    possible_duplicates: [],
    attendance_changed: 2,
  },
  requires_removal_confirmation: true,
};

export const scoresPreview: ImportPreview = {
  import_id: 4,
  kind: 'scores',
  filename: 'scores_2026-10-04.xlsx',
  duplicate_of: null,
  findings: [],
  diff: {
    events_added: ['2026-10-04'],
    events_removed: [],
    rows_added: 22,
    rows_removed: 0,
    rows_changed: 1,
    new_names: ['Newman, Pat'],
    possible_duplicates: [['Hamond, Bennett', 'Hammond, Bennett']],
    attendance_changed: 1,
  },
  requires_removal_confirmation: false,
};

export const stationsPreview: ImportPreview = {
  import_id: 5,
  kind: 'stations',
  filename: 'stations_variant.xlsx',
  duplicate_of: null,
  findings: [
    {
      code: 'station_score_mismatch',
      severity: 'warning',
      message: 'Station total 31 vs score 30',
      sheet: '9 6 26',
      row: 31,
      event_date: '2026-09-06',
      name: 'Marsden, Wylie',
    },
  ],
  diff: {
    events_added: [],
    events_replaced: ['2026-09-06'],
    events_unchanged: [],
    sheets_skipped: ['9 20 26'],
  },
  requires_removal_confirmation: false,
};

/** Plan 17: the special-shoot diff on its own, typed so tests can spread and override fields. */
export const specialDiff: SpecialDiff = {
  event_date: '2026-09-20',
  label: '3-Bird Shoot',
  target_total: 60,
  stations: ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10'],
  n_shooters: 5,
  replaces_import: null,
  regular_rows_on_date: 0,
  new_names: ['Kim, Pat'],
  possible_duplicates: [['Kim, Pat', 'Kimm, Pat']],
};

/** Plan 17: a special-shoot workbook's preview (invented names). */
export const specialPreview: ImportPreview = {
  import_id: 6,
  kind: 'special',
  filename: 'special_2026-09-20.xlsx',
  duplicate_of: null,
  findings: [
    {
      code: 'special_total_mismatch',
      severity: 'warning',
      message: 'Total 50 does not match the station hits (51); the hits are used',
      sheet: 'Special Event',
      row: 6,
      event_date: '2026-09-20',
      name: 'Kaplan, Noel',
    },
  ],
  diff: specialDiff,
  requires_removal_confirmation: false,
};

/**
 * Re-upload of the committed stations file: Plan 03 (Decision 7) stages nothing and returns import #2's stored
 * preview with `import_id === duplicate_of` and its original filename.
 */
export const duplicatePreview: ImportPreview = {
  import_id: 2,
  kind: 'stations',
  filename: 'stations_2026-09-27.xlsx',
  duplicate_of: 2,
  findings: [],
  diff: {
    events_added: ['2026-09-06', '2026-09-13'],
    events_replaced: [],
    events_unchanged: [],
    sheets_skipped: [],
  },
  requires_removal_confirmation: false,
};

export const doneJob: Job = {
  id: 41,
  kind: 'rebuild',
  status: 'done',
  attempts: 1,
  error: null,
  created_at: '2026-09-27T19:01:00Z',
  started_at: '2026-09-27T19:01:01Z',
  finished_at: '2026-09-27T19:01:04Z',
};

/** Every Plan 06 ShooterSummaryOut field; Hadley is fixture data, "Crimson, Al" an illustrative guest. */
export const shooterMatches: ShooterMatch[] = [
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
    shooter_id: 90,
    display_name: 'Crimson, Al',
    status: 'guest',
    n_rounds: 1,
    n_events: 1,
    first_event: '2025-02-23',
    last_event: '2025-02-23',
    active: false,
    mu: null,
  },
];

// Default handlers: branch-free, exercised by routes.test.tsx. /api/shooters belongs to features/shooters.
export const handlers = [
  http.get('*/api/admin/imports', () => HttpResponse.json(importsList)),
  http.get('*/api/admin/imports/:id', ({ params }) =>
    HttpResponse.json({ ...stalePreview, import_id: Number(params.id) }),
  ),
  http.post('*/api/admin/imports', () => HttpResponse.json(scoresPreview)),
  http.post('*/api/admin/imports/:id/commit', () => HttpResponse.json({ job_id: 41 })),
  http.post('*/api/admin/imports/:id/discard', () => new HttpResponse(null, { status: 204 })),
  http.post('*/api/admin/imports/:id/rollback', () => HttpResponse.json({ job_id: 42 })),
  http.get('*/api/admin/jobs/:id', ({ params }) =>
    HttpResponse.json({ ...doneJob, id: Number(params.id) }),
  ),
];
