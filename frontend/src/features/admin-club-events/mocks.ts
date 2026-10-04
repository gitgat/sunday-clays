import { http, HttpResponse } from 'msw';
import type { AdminEvent, AdminRosterRow, Contact } from './api';

export const adminEvent: AdminEvent = {
  id: 1,
  title: 'Fall Fun Shoot',
  starts_at: '2026-10-18T06:30:00Z',
  local_date: '2026-10-17',
  local_time: '23:30',
  signup_deadline: '2026-10-17T03:00:00Z',
  deadline_local_date: '2026-10-16',
  deadline_local_time: '20:00',
  state: 'open',
  upcoming: true,
  capacity: 20,
  spots_taken: 2,
  waitlist_count: 1,
  allow_guests: true,
  max_guests: 2,
  signups: 1,
  purged: false,
  notes: 'Bring eye and ear protection.',
};

const base = {
  promoted_at: null,
  cancelled_at: null,
  cancelled_via: null,
  cancel_fail_count: 0,
  signed_up_at: '2026-10-02T18:05:00Z',
  signed_up_local: '2026-10-02 11:05',
} as const;

export const rosterRows: AdminRosterRow[] = [
  {
    ...base,
    id: 41,
    name: 'Hadley, Ike',
    typed_name: null,
    shooter_id: 3,
    email: 'ike.hadley@example.com',
    email_source: 'contact',
    guests: 1,
    status: 'going',
    waitlist_position: null,
    suggested_shooter: null,
  },
  {
    ...base,
    id: 42,
    name: 'Ike Hadly',
    typed_name: 'Ike Hadly',
    shooter_id: null,
    email: 'ike.typo@example.com',
    email_source: 'registration',
    guests: 2,
    status: 'waitlist',
    waitlist_position: 1,
    suggested_shooter: { id: 3, name: 'Hadley, Ike', has_email: true },
  },
  {
    ...base,
    id: 43,
    name: 'Pat Kim',
    typed_name: 'Pat Kim',
    shooter_id: null,
    email: null,
    email_source: null,
    guests: 0,
    status: 'cancelled',
    waitlist_position: null,
    cancelled_at: '2026-10-02T19:00:00Z',
    cancelled_via: 'device',
    suggested_shooter: null,
  },
];

export const contacts: Contact[] = [
  {
    shooter_id: 3,
    name: 'Hadley, Ike',
    email: 'ike.hadley@example.com',
    source: 'signup',
    updated_at: '2026-09-27T18:00:00Z',
    last_used_at: '2026-10-02T03:00:00Z',
    last_used_on: '2026-10-01',
  },
];

export const handlers = [
  http.get('*/api/admin/club-events', () => HttpResponse.json([adminEvent])),
  http.get('*/api/admin/club-events/:id/roster', () => HttpResponse.json(rosterRows)),
  http.get(
    '*/api/admin/club-events/:id/roster.csv',
    () =>
      new HttpResponse(
        'status,waitlist_position,name,shooter_id,email,guests,spots,signed_up_local\r\n',
        {
          headers: { 'Content-Type': 'text/csv; charset=utf-8' },
        },
      ),
  ),
  http.get('*/api/admin/club-events/:id/emails', () => HttpResponse.json({ emails: [] })),
  http.get('*/api/admin/shooter-contacts', () => HttpResponse.json(contacts)),
];
