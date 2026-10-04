import { describe, expect, it } from 'vitest';
import {
  cameLine,
  cancelOwnQuestion,
  chipText,
  deadlineLine,
  formatEventDate,
  formatEventTime,
  guestsRule,
  rosterSummary,
  spotsLine,
  statusLine,
  whenLine,
} from './format';
import { fallFunShoot } from './mocks';

describe('club-event copy (§5.8), from club-time parts only (D21)', () => {
  it('formats the date and time as calendar parts', () => {
    expect(formatEventDate('2026-10-17')).toBe('Sat, Oct 17');
    expect(formatEventTime('23:30')).toBe('11:30 PM');
    expect(formatEventTime('09:00')).toBe('9:00 AM');
    expect(formatEventTime('00:15')).toBe('12:15 AM');
    expect(formatEventTime('12:00')).toBe('12:00 PM');
    expect(whenLine(fallFunShoot)).toBe('Sat, Oct 17 · 11:30 PM');
  });

  it('says the deadline while open, then closed, or nothing', () => {
    expect(deadlineLine(fallFunShoot)).toBe('Sign up by Fri, Oct 16, 8:00 PM');
    expect(deadlineLine({ ...fallFunShoot, state: 'closed' })).toBe('Sign-ups closed');
    expect(deadlineLine({ ...fallFunShoot, state: 'started', upcoming: false })).toBeNull();
    expect(deadlineLine({ ...fallFunShoot, state: 'cancelled' })).toBeNull();
  });

  it('counts spots with and without a capacity', () => {
    const e = { capacity: 20, spots_taken: 12, waitlist_count: 0 };
    expect(spotsLine(e)).toBe('12 of 20 spots taken');
    expect(spotsLine({ ...e, spots_taken: 20, waitlist_count: 3 })).toBe(
      'Full · 3 on the waitlist',
    );
    expect(spotsLine({ ...e, spots_taken: 20 })).toBe('Full · join the waitlist');
    expect(spotsLine({ capacity: null, spots_taken: 14, waitlist_count: 0 })).toBe('14 going');
    expect(spotsLine({ capacity: null, spots_taken: 1, waitlist_count: 0 })).toBe('1 going');
    expect(rosterSummary({ ...e, waitlist_count: 3 })).toBe(
      '12 of 20 spots taken · 3 on the waitlist',
    );
    expect(rosterSummary(e)).toBe('12 of 20 spots taken');
  });

  it('states the guest rule, the status, the chip and the cancel question', () => {
    expect(guestsRule({ allow_guests: true, max_guests: 2 })).toBe('Guests welcome, up to 2 each');
    expect(guestsRule({ allow_guests: false, max_guests: 0 })).toBe('Members only, no guests');
    const going = { status: 'going', guests: 0, waitlist_position: null } as const;
    expect(statusLine(going)).toBe("You're in. See you there!");
    expect(statusLine({ ...going, guests: 1 })).toBe("You're in, plus 1 guest. See you there!");
    expect(statusLine({ ...going, guests: 2 })).toBe("You're in, plus 2 guests. See you there!");
    const waiting = { status: 'waitlist', guests: 0, waitlist_position: 3 } as const;
    expect(statusLine(waiting)).toBe(
      "You're on the waitlist: #3. If a spot opens, you move up automatically.",
    );
    expect(chipText(going)).toBe("You're in");
    expect(chipText({ ...waiting, waitlist_position: 2 })).toBe('Waitlist #2');
    expect(cancelOwnQuestion(0)).toBe('Cancel your spot?');
    expect(cancelOwnQuestion(2)).toBe('Cancel your spot and 2 guests?');
    expect(cameLine({ signups: 28 })).toBe('28 came');
  });
});

describe('club-event copy once the event is past (Ruling F3)', () => {
  it('says nothing present-tense or actionable for a past event', () => {
    for (const state of ['closed', 'started', 'open'] as const) {
      expect(deadlineLine({ ...fallFunShoot, state, upcoming: false })).toBeNull();
    }
    const full = { capacity: 20, spots_taken: 20, waitlist_count: 0 };
    expect(spotsLine({ ...full, upcoming: false })).toBe('Full');
    expect(spotsLine({ ...full, upcoming: true, state: 'closed' })).toBe('Full');
    expect(spotsLine({ ...full, upcoming: true, state: 'open' })).toBe('Full · join the waitlist');
    const going = { status: 'going', guests: 0, waitlist_position: null } as const;
    const past = { upcoming: false, state: 'started' } as const;
    expect(statusLine(going, past)).toBe('You signed up.');
    expect(statusLine({ ...going, guests: 2 }, past)).toBe('You signed up, plus 2 guests.');
    expect(statusLine({ ...going, status: 'waitlist' }, past)).toBe('You were on the waitlist.');
  });

  it('says a past cancelled event was cancelled, in the past tense, and keeps no spot', () => {
    const going = { status: 'going', guests: 0, waitlist_position: null } as const;
    expect(statusLine(going, { upcoming: false, state: 'cancelled' })).toBe(
      'This club event was cancelled.',
    );
  });

  it('keeps the spot for a cancelled event and never says see you there', () => {
    const going = { status: 'going', guests: 0, waitlist_position: null } as const;
    const text = statusLine(going, { upcoming: true, state: 'cancelled' });
    expect(text).toBe('Your spot is kept in case the organizers restore this club event.');
    expect(
      statusLine({ ...going, status: 'waitlist' }, { upcoming: true, state: 'cancelled' }),
    ).toBe(text);
  });
});

describe('club-event copy edge cases', () => {
  it('leaves the place blank rather than saying "null" if the server omits it', () => {
    const row = { status: 'waitlist', guests: 0, waitlist_position: null } as const;
    expect(statusLine(row)).toBe(
      "You're on the waitlist. If a spot opens, you move up automatically.",
    );
    expect(chipText(row)).toBe('On the waitlist');
  });

  it('returns the raw text for a date it cannot read instead of throwing', () => {
    expect(formatEventDate('not-a-date')).toBe('not-a-date');
  });
});
