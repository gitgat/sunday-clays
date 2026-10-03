import { afterEach, describe, expect, it, vi } from 'vitest';
import { installChunkReload, RELOAD_KEY } from './chunkReload';

function fakeWindow() {
  const target = new EventTarget();
  const reload = vi.fn();
  const win = Object.assign(target, { location: { reload }, sessionStorage }) as unknown as Window;
  return { win, reload, target };
}

afterEach(() => sessionStorage.clear());

describe('chunk-load recovery', () => {
  it('reloads once on a preload error, and not twice', () => {
    const { win, reload, target } = fakeWindow();
    installChunkReload(win);
    const first = new Event('vite:preloadError', { cancelable: true });
    target.dispatchEvent(first);
    expect(reload).toHaveBeenCalledTimes(1);
    expect(first.defaultPrevented).toBe(true);
    expect(sessionStorage.getItem(RELOAD_KEY)).toBe('1');
    target.dispatchEvent(new Event('vite:preloadError', { cancelable: true }));
    expect(reload).toHaveBeenCalledTimes(1);
  });

  it('never reloads when the guard cannot be stored (no reload loop)', () => {
    const { win, reload, target } = fakeWindow();
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('blocked');
    });
    installChunkReload(win);
    target.dispatchEvent(new Event('vite:preloadError', { cancelable: true }));
    expect(reload).not.toHaveBeenCalled();
    vi.restoreAllMocks();
  });

  it('clears the guard after a successful load', () => {
    const { win, target } = fakeWindow();
    sessionStorage.setItem(RELOAD_KEY, '1');
    installChunkReload(win);
    target.dispatchEvent(new Event('load'));
    expect(sessionStorage.getItem(RELOAD_KEY)).toBeNull();
  });
});
