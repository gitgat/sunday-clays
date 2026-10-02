import { useEffect } from 'react';
import { useLocation } from 'react-router';
import type { components } from '../../api/schema';
import { getDeviceId } from '../../lib/device';
import { getMe, isMeSkipped } from '../../lib/me';
import type { Role } from '../auth/api';
import { pageKind } from './pageKind';

export type PageView = components['schemas']['PageViewIn'];
export type MeState = PageView['me_state'];

export const PAGE_VIEWS_PATH = '/api/pageviews';

/** "Which one are you?" as a state, never the name: picked, skipped or not answered yet. */
export function meState(): MeState {
  if (getMe() !== null) return 'picked';
  return isMeSkipped() ? 'skipped' : 'none';
}

/**
 * Fire-and-forget POST of one page view. Same-origin (CSP connect-src 'self'), keepalive so it
 * outlives the page, and never awaited. It never throws and never redirects to the login page:
 * the openapi client would on a 401 (Decision 15).
 */
export function sendPageView(view: PageView): void {
  try {
    void globalThis
      .fetch(PAGE_VIEWS_PATH, {
        method: 'POST',
        keepalive: true,
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(view),
      })
      .catch(() => undefined);
  } catch {
    // fetch itself threw: page views are best-effort.
  }
}

/**
 * One page view per client-side page change (the pathname, not the query string), sent after
 * paint. Admin sessions and browsers that cannot keep a device id send nothing; the server also
 * drops admin views, and dedupes a device on a kind for 30 minutes.
 */
export function usePageViewBeacon(role: Role | null): void {
  const { pathname } = useLocation();
  useEffect(() => {
    if (role !== 'viewer') return;
    const deviceId = getDeviceId();
    if (deviceId === null) return;
    sendPageView({
      device_id: deviceId,
      page_kind: pageKind(pathname),
      me_state: meState(),
      at: new Date().toISOString(),
    });
  }, [pathname, role]);
}
