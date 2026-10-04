import { renderHook, act } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  acknowledgePromotions,
  allSignups,
  forgetEvent,
  forgetSignup,
  pruneTo,
  readPastOpen,
  reconcile,
  saveSignup,
  signupsFor,
  TOKENS_KEY,
  useDeviceSignups,
  writePastOpen,
} from './tokens';

afterEach(() => {
  vi.restoreAllMocks();
});

describe('device sign-up tokens (D10a)', () => {
  it('saves, lists, forgets', () => {
    saveSignup(21, { eventId: 1, token: 'tok-21', status: 'going' });
    saveSignup(22, { eventId: 2, token: 'tok-22', status: 'waitlist' });
    expect(signupsFor(1)).toEqual([
      { registrationId: 21, eventId: 1, token: 'tok-21', status: 'going' },
    ]);
    forgetSignup(21);
    expect(allSignups().map((s) => s.registrationId)).toEqual([22]);
    forgetEvent(2);
    expect(allSignups()).toEqual([]);
  });

  it("a removed sign-up's token is dropped and a new sign-up is the one cancelled", () => {
    saveSignup(21, { eventId: 1, token: 'old', status: 'going' });
    expect(reconcile(1, [])).toBe(false); // removed by an organizer: no longer listed
    saveSignup(30, { eventId: 1, token: 'new', status: 'going' });
    reconcile(1, [{ registration_id: 30, status: 'going' }]);
    expect(signupsFor(1).map((s) => [s.registrationId, s.token])).toEqual([[30, 'new']]);
  });

  it('marks a waitlist sign-up that is now going until it is acknowledged', () => {
    saveSignup(21, { eventId: 1, token: 'tok', status: 'waitlist' });
    expect(reconcile(1, [{ registration_id: 21, status: 'going' }])).toBe(true);
    expect(signupsFor(1)[0]).toMatchObject({ status: 'going', promoted: true });
    expect(reconcile(1, [{ registration_id: 21, status: 'going' }])).toBe(false);
    acknowledgePromotions(1);
    expect(signupsFor(1)[0]?.promoted).toBeUndefined();
  });

  it('prunes tokens for events that are gone or purged, keeping the rest', () => {
    saveSignup(1, { eventId: 1, token: 'a', status: 'going' });
    saveSignup(2, { eventId: 2, token: 'b', status: 'going' });
    saveSignup(3, { eventId: 3, token: 'c', status: 'going' });
    pruneTo([1, 2], [2]); // 3 is not listed any more, 2 was purged
    expect(allSignups().map((s) => s.registrationId)).toEqual([1]);
  });

  it('ignores junk in storage', () => {
    localStorage.setItem(TOKENS_KEY, JSON.stringify({ '5': { eventId: 'x' }, '6': 'nope' }));
    expect(allSignups()).toEqual([]);
    localStorage.setItem(TOKENS_KEY, '{not json');
    expect(allSignups()).toEqual([]);
  });

  it('works with storage that throws', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new DOMException('blocked', 'SecurityError');
    });
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new DOMException('blocked', 'SecurityError');
    });
    expect(() => saveSignup(1, { eventId: 1, token: 't', status: 'going' })).not.toThrow();
    expect(allSignups()).toEqual([]);
    expect(readPastOpen()).toBe(false);
    expect(() => writePastOpen(true)).not.toThrow();
  });

  it('remembers the past-events disclosure per device', () => {
    expect(readPastOpen()).toBe(false);
    writePastOpen(true);
    expect(readPastOpen()).toBe(true);
  });

  it('re-renders subscribers when tokens change', () => {
    const { result } = renderHook(() => useDeviceSignups());
    expect(result.current).toEqual([]);
    act(() => saveSignup(9, { eventId: 4, token: 't9', status: 'going' }));
    expect(result.current.map((s) => s.registrationId)).toEqual([9]);
  });
});

describe('device sign-up tokens, edge cases', () => {
  it('ignores a stored value that is not an object', () => {
    localStorage.setItem(TOKENS_KEY, 'null');
    expect(allSignups()).toEqual([]);
    localStorage.setItem(TOKENS_KEY, '5');
    expect(allSignups()).toEqual([]);
  });

  it("leaves other events' tokens alone when reconciling or acknowledging", () => {
    saveSignup(21, { eventId: 1, token: 'a', status: 'waitlist' });
    saveSignup(22, { eventId: 2, token: 'b', status: 'waitlist' });
    expect(reconcile(1, [{ registration_id: 21, status: 'going' }])).toBe(true);
    acknowledgePromotions(1);
    expect(signupsFor(2)).toEqual([
      { registrationId: 22, eventId: 2, token: 'b', status: 'waitlist' },
    ]);
  });

  it('remembers the disclosure closed again', () => {
    writePastOpen(true);
    writePastOpen(false);
    expect(readPastOpen()).toBe(false);
  });
});
