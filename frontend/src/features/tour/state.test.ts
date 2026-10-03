import { afterEach, describe, expect, it, vi } from 'vitest';
import { isTourDone, markTourDone, resetTourForTests, subscribeTour, TOUR_KEY } from './state';

afterEach(() => resetTourForTests());

describe('tour state', () => {
  it('is done once marked, and remembered in localStorage', () => {
    expect(isTourDone()).toBe(false);
    markTourDone();
    expect(isTourDone()).toBe(true);
    expect(localStorage.getItem(TOUR_KEY)).toBe('done');
  });

  it('reads a stored "done"', () => {
    localStorage.setItem(TOUR_KEY, 'done');
    expect(isTourDone()).toBe(true);
  });

  it('notifies subscribers', () => {
    const listener = vi.fn();
    const unsubscribe = subscribeTour(listener);
    markTourDone();
    expect(listener).toHaveBeenCalledTimes(1);
    unsubscribe();
    markTourDone();
    expect(listener).toHaveBeenCalledTimes(1);
  });

  it('falls back to memory when storage throws (at most once per load)', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('blocked');
    });
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('blocked');
    });
    expect(isTourDone()).toBe(false);
    markTourDone();
    expect(isTourDone()).toBe(true);
  });
});
