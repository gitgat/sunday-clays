import { http, HttpResponse } from 'msw';
import type { ClubEventDetail, ClubEventList, ClubEventSummary, SignupResult } from './api';

/** Sat Oct 17, 23:30 club time (2026-10-18T06:30Z): the D21 late-evening case. */
export const fallFunShoot: ClubEventDetail = {
  id: 1,
  title: 'Fall Fun Shoot',
  starts_at: '2026-10-18T06:30:00Z',
  local_date: '2026-10-17',
  local_time: '23:30',
  signup_deadline: '2026-10-17T03:00:00Z',
  deadline_local_date: '2026-10-16',
  deadline_local_time: '20:00',
  state: 'open',
  capacity: 4,
  spots_taken: 3,
  waitlist_count: 1,
  allow_guests: true,
  max_guests: 2,
  signups: 2,
  purged: false,
  notes: 'Bring eye and ear protection.\nLunch at noon.',
  roster: [
    {
      registration_id: 11,
      name: 'Hadley, Ike',
      shooter_id: 3,
      guests: 1,
      status: 'going',
      waitlist_position: null,
    },
    {
      registration_id: 12,
      name: 'Dana Quill',
      shooter_id: null,
      guests: 0,
      status: 'going',
      waitlist_position: null,
    },
    {
      registration_id: 13,
      name: 'Pat Kim',
      shooter_id: null,
      guests: 1,
      status: 'waitlist',
      waitlist_position: 1,
    },
  ],
};

export function toSummary(detail: ClubEventDetail): ClubEventSummary {
  const copy: ClubEventSummary & Partial<Pick<ClubEventDetail, 'notes' | 'roster'>> = { ...detail };
  delete copy.notes;
  delete copy.roster;
  return copy;
}

export const fallFunSummary: ClubEventSummary = toSummary(fallFunShoot);

export const banquetPast: ClubEventSummary = {
  ...fallFunSummary,
  id: 2,
  title: 'Summer Banquet',
  starts_at: '2026-08-02T01:00:00Z',
  local_date: '2026-08-01',
  local_time: '18:00',
  state: 'started',
  capacity: null,
  spots_taken: 31,
  waitlist_count: 0,
  signups: 28,
  purged: true,
};

export const clubEventList: ClubEventList = { upcoming: [fallFunSummary], past: [banquetPast] };

export const signedUp: SignupResult = {
  registration_id: 21,
  token: 'tok-21',
  status: 'going',
  waitlist_position: null,
  email_used: 'given',
};

export const handlers = [
  http.get('*/api/club-events', () => HttpResponse.json(clubEventList)),
  http.get('*/api/club-events/:id', ({ params }) =>
    HttpResponse.json({ ...fallFunShoot, id: Number(params.id) }),
  ),
  http.get('*/api/club-events/:id/signup-check', () =>
    HttpResponse.json({ has_email: false, already_signed_up: false }),
  ),
  http.post('*/api/club-events/:id/registrations', () =>
    HttpResponse.json(signedUp, { status: 201 }),
  ),
  http.post('*/api/club-events/:id/registrations/:rid/cancel', () =>
    HttpResponse.json({ status: 'cancelled', promoted: 0 }),
  ),
];
