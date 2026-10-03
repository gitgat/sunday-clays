/**
 * Plan 19 §3.4: a lazy chunk from an old build that is gone from both the cache and the server
 * reloads the page onto the new build, instead of showing an error. Guarded by a timestamp: at
 * most one reload per 30 s, so a chunk that keeps failing (an installed app opened offline, a
 * deploy race) cannot loop. Chunk failures arrive after the window `load` event, so the guard is
 * never cleared on load; it simply expires.
 */
export const RELOAD_KEY = 'sc.chunk.reloaded';
const RELOAD_WINDOW_MS = 30_000;

export function installChunkReload(win: Window = window): void {
  win.addEventListener('vite:preloadError', (event) => {
    try {
      const last = Number(win.sessionStorage.getItem(RELOAD_KEY));
      const now = Date.now();
      if (Number.isFinite(last) && now - last < RELOAD_WINDOW_MS) return; // the route's error page shows
      win.sessionStorage.setItem(RELOAD_KEY, String(now));
    } catch {
      return; // no guard can be kept (storage blocked): never risk a reload loop
    }
    event.preventDefault();
    win.location.reload();
  });
}
