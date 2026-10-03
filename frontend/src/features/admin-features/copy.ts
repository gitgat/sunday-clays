import { formatDate } from '../../lib/format';
import type { PageCacheStatus } from './api';

export const FEATURES_INTRO =
  'Turn a finished feature on for everyone. While a switch is off, only admins see the feature, marked “Admin preview”. Changes reach everyone within a minute. No redeploy needed.';

/** "Changed Oct 2, 2026" from the club-timezone date (D26), or "Never changed". */
export function changedText(updatedOn: string | null): string {
  return updatedOn === null ? 'Never changed' : `Changed ${formatDate(updatedOn)}`;
}

export const INFRA_INTRO =
  'Behind-the-scenes settings. They change how fast pages open, never what they show.';

/** The status line under "Page cache" (§3.7.6); dates come from the club-timezone local_date. */
export function cacheStatusText(status: PageCacheStatus): string {
  if (status.forced_off) return 'Turned off on the server';
  if (!status.enabled) return 'Off. Pages compute live and nothing is stored.';
  const warm = status.last_warm;
  if (warm === null) return 'Not refreshed yet';
  if (
    warm.data_version !== status.current.data_version ||
    warm.local_date !== status.current.local_date
  ) {
    return 'Refreshing…';
  }
  const megabytes = Math.round(status.bytes / 1_000_000);
  const trouble = [
    warm.failed > 0 ? `${String(warm.failed)} ${warm.failed === 1 ? 'page' : 'pages'} failed` : '',
    warm.skipped > 0 ? `${String(warm.skipped)} skipped` : '',
  ].filter((part) => part !== '');
  const problems = trouble.length > 0 ? ` · ${trouble.join(', ')}` : '';
  return `${status.rows.toLocaleString('en-US')} pages stored · ${String(megabytes)} MB · last refreshed ${formatDate(warm.local_date)} (${String(warm.warmed)} pages in ${String(Math.round(warm.seconds))} s)${problems}`;
}
