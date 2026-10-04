import { describe, expect, it } from 'vitest';
import { defaultDeadline, headHint, notesCounter, sourceLabel, statusLabel, toBody } from './form';
import { rosterRows } from './mocks';

describe('organizer form helpers', () => {
  it('defaults the deadline to 20:00 the day before, across months and years', () => {
    expect(defaultDeadline('2026-10-17')).toEqual({ date: '2026-10-16', time: '20:00' });
    expect(defaultDeadline('2026-11-01')).toEqual({ date: '2026-10-31', time: '20:00' });
    expect(defaultDeadline('2027-01-01')).toEqual({ date: '2026-12-31', time: '20:00' });
  });

  it('counts notes against the 2,000 limit', () => {
    expect(notesCounter(1840)).toBe('1,840 / 2,000');
    expect(notesCounter(0)).toBe('0 / 2,000');
  });

  it('builds the API body from the form', () => {
    const body = toBody({
      title: ' Fall Fun Shoot ',
      date: '2026-10-17',
      time: '10:00',
      deadlineDate: '2026-10-16',
      deadlineTime: '20:00',
      notes: 'Bring a chair.',
      capacity: '',
      allowGuests: false,
      maxGuests: '2',
    });
    expect(body).toEqual({
      title: 'Fall Fun Shoot',
      starts_local: '2026-10-17T10:00',
      deadline_local: '2026-10-16T20:00',
      notes: 'Bring a chair.',
      capacity: null,
      allow_guests: false,
      max_guests: 0,
    });
    const withLimit = toBody({
      title: 'x',
      date: '2026-10-17',
      time: '10:00',
      deadlineDate: '2026-10-16',
      deadlineTime: '20:00',
      notes: '',
      capacity: '20',
      allowGuests: true,
      maxGuests: '2',
    });
    expect(withLimit).toMatchObject({ capacity: 20, max_guests: 2 });
  });

  it('says when the waitlist head does not fit the open spots', () => {
    expect(headHint(rosterRows, 3)).toBe('1 spot open; the next sign-up on the waitlist needs 3.');
    expect(headHint(rosterRows, 6)).toBeNull();
    expect(headHint(rosterRows, null)).toBeNull();
  });

  it('labels status and source', () => {
    expect(rosterRows.map(statusLabel)).toEqual(['Going', 'Waitlist #1', 'Cancelled']);
    expect(rosterRows.map(sourceLabel)).toEqual(['List', 'New name', 'New name']);
  });
});
