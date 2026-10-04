import { afterEach, describe, expect, it, vi } from 'vitest';
import { installChunkReload, RELOAD_KEY } from './chunkReload';

function fakeWindow() {
  const target = new EventTarget();
  const reload = vi.fn();
  const win = Object.assign(target, { location: { reload }, sessionStorage }) as unknown as Window;
  return { win, reload, target };
}

afterEach(() => sessionStorage.clear());

const fail = (target: EventTarget) =>
  target.dispatchEvent(new Event('vite:preloadError', { cancelable: true }));

describe('chunk-load recovery', () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  it('reloads on a preload error and stamps the time', () => {
    vi.useFakeTimers({ now: 1_000_000 });
    const { win, reload, target } = fakeWindow();
    installChunkReload(win);
    const first = new Event('vite:preloadError', { cancelable: true });
    target.dispatchEvent(first);
    expect(reload).toHaveBeenCalledTimes(1);
    expect(first.defaultPrevented).toBe(true);
    expect(sessionStorage.getItem(RELOAD_KEY)).toBe('1000000');
  });

  it('does not loop: a failure right after the reloaded page loads does not reload again', () => {
    vi.useFakeTimers({ now: 1_000_000 });
    const { win, reload, target } = fakeWindow();
    installChunkReload(win);
    fail(target);
    target.dispatchEvent(new Event('load')); // lazy-chunk failures arrive after load
    vi.advanceTimersByTime(1000);
    const again = new Event('vite:preloadError', { cancelable: true });
    target.dispatchEvent(again);
    expect(reload).toHaveBeenCalledTimes(1);
    expect(again.defaultPrevented).toBe(false); // the route's error page shows
  });

  it('reloads again once 30 seconds have passed', () => {
    vi.useFakeTimers({ now: 1_000_000 });
    const { win, reload, target } = fakeWindow();
    installChunkReload(win);
    fail(target);
    vi.advanceTimersByTime(29_999);
    fail(target);
    expect(reload).toHaveBeenCalledTimes(1);
    vi.advanceTimersByTime(1);
    fail(target);
    expect(reload).toHaveBeenCalledTimes(2);
  });

  it('reloads when the stamp is ahead of the clock (the clock was corrected backwards)', () => {
    vi.useFakeTimers({ now: 1_000_000 });
    sessionStorage.setItem(RELOAD_KEY, '5000000');
    const { win, reload, target } = fakeWindow();
    installChunkReload(win);
    fail(target);
    expect(reload).toHaveBeenCalledTimes(1);
    expect(sessionStorage.getItem(RELOAD_KEY)).toBe('1000000');
  });

  it('treats an unreadable stamp as no earlier reload', () => {
    sessionStorage.setItem(RELOAD_KEY, 'junk');
    const { win, reload, target } = fakeWindow();
    installChunkReload(win);
    fail(target);
    expect(reload).toHaveBeenCalledTimes(1);
  });

  it('never reloads when the guard cannot be stored (no reload loop)', () => {
    const { win, reload, target } = fakeWindow();
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('blocked');
    });
    installChunkReload(win);
    fail(target);
    expect(reload).not.toHaveBeenCalled();
  });
});
