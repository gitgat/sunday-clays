/**
 * Plan 19 §3.4: a lazy chunk from an old build that is gone from both the cache and the server
 * reloads the page once onto the new build, instead of showing an error. Guarded per session.
 */
export const RELOAD_KEY = 'sc.chunk.reloaded';

export function installChunkReload(win: Window = window): void {
  win.addEventListener('vite:preloadError', (event) => {
    try {
      if (win.sessionStorage.getItem(RELOAD_KEY) === '1') return; // the error stands: the route's error page shows
      win.sessionStorage.setItem(RELOAD_KEY, '1');
    } catch {
      return; // no guard can be kept (storage blocked): never risk a reload loop
    }
    event.preventDefault();
    win.location.reload();
  });
  win.addEventListener('load', () => {
    try {
      win.sessionStorage.removeItem(RELOAD_KEY);
    } catch {
      // storage blocked: nothing to clear
    }
  });
}
