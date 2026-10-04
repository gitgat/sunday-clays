import { afterEach, describe, expect, it, vi } from 'vitest';
import { adminEvent, rosterRows } from './mocks';
import { CONTACT_SOURCES, fromEvent, headHint, sortEvents, statusLabel } from './form';

afterEach(() => {
  vi.useRealTimers();
});

describe('organizer form helpers, edges', () => {
  it('starts a new form empty and an edit form from the event', () => {
    expect(fromEvent(null)).toMatchObject({
      title: '',
      capacity: '',
      allowGuests: false,
      maxGuests: '1',
    });
    expect(fromEvent(adminEvent)).toMatchObject({
      title: 'Fall Fun Shoot',
      capacity: '20',
      maxGuests: '2',
    });
    expect(
      fromEvent({ ...adminEvent, capacity: null, allow_guests: false, max_guests: 0 }),
    ).toMatchObject({
      capacity: '',
      maxGuests: '1',
    });
  });

  it('has no hint without a waitlist, without room, or when the head fits', () => {
    const going = rosterRows.filter((r) => r.status === 'going');
    expect(headHint(going, 20)).toBeNull();
    expect(headHint(rosterRows, 2)).toBeNull();
    expect(headHint(rosterRows, 10)).toBeNull();
    expect(headHint(rosterRows, 4)).toBe('2 spots open; the next sign-up on the waitlist needs 3.');
  });

  it('looks at the first on the waitlist, a position of none counts as first, whatever the order', () => {
    const [a, b] = [rosterRows[1], rosterRows[1]];
    if (a === undefined || b === undefined) throw new Error('fixture');
    const rows = [
      { ...a, id: 50, guests: 0, waitlist_position: 2 },
      { ...b, id: 51, guests: 2, waitlist_position: 1 },
      { ...b, id: 52, guests: 5, waitlist_position: null },
    ];
    expect(headHint(rows, 4)).toBe('4 spots open; the next sign-up on the waitlist needs 6.');
    expect(headHint([...rows].reverse(), 4)).toBe(
      '4 spots open; the next sign-up on the waitlist needs 6.',
    );
  });

  it('labels a removed sign-up and names every contact source', () => {
    const [first] = rosterRows;
    expect(first && statusLabel({ ...first, status: 'removed' })).toBe('Removed');
    expect(first && statusLabel({ ...first, status: 'waitlist', waitlist_position: null })).toBe(
      'Waitlist #',
    );
    expect(CONTACT_SOURCES).toEqual({ signup: 'Sign-up', organizer: 'Organizer', link: 'Linked' });
  });

  it("splits upcoming from past on the server's flag, not the device clock", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-12-31T00:00:00Z'));
    const at = (id: number, starts_at: string, upcoming: boolean) => ({
      ...adminEvent,
      id,
      starts_at,
      upcoming,
    });
    const sorted = sortEvents([
      at(1, '2026-09-01T00:00:00Z', false),
      at(2, '2026-11-01T00:00:00Z', true),
      at(3, '2026-10-20T00:00:00Z', true),
      at(4, '2026-09-20T00:00:00Z', false),
    ]);
    expect(sorted.map((e) => e.id)).toEqual([3, 2, 4, 1]);
  });
});
