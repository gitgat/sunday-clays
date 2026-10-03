import { useEffect } from 'react';
import { useFeature } from '../../lib/features';
import { useSession } from '../auth/api';

export const MANIFEST_HREF = '/manifest.webmanifest';
export const SHELL_CACHE_PREFIX = 'sc-shell-';

function linkManifest(): void {
  if (document.querySelector('link[rel="manifest"]') !== null) return;
  const link = document.createElement('link');
  link.rel = 'manifest';
  link.href = MANIFEST_HREF;
  document.head.appendChild(link);
}

function unlinkManifest(): void {
  document.querySelectorAll('link[rel="manifest"]').forEach((el) => el.remove());
}

async function registerShell(): Promise<void> {
  if (!('serviceWorker' in navigator)) return;
  await navigator.serviceWorker.register('/sw.js', { scope: '/' }).catch(() => undefined);
}

async function removeShell(): Promise<void> {
  await removeShellUnsafe().catch(() => undefined); // a failed clean-up retries on the next load
}

async function removeShellUnsafe(): Promise<void> {
  if ('serviceWorker' in navigator) {
    const registrations = await navigator.serviceWorker.getRegistrations();
    await Promise.all(registrations.map((r) => r.unregister()));
  }
  if ('caches' in window) {
    const names = await caches.keys();
    await Promise.all(
      names.filter((n) => n.startsWith(SHELL_CACHE_PREFIX)).map((n) => caches.delete(n)),
    );
  }
}

/**
 * Plan 19 D16: link the manifest and register /sw.js only while `pwa` is visible. Unregister
 * only on a definite off: a successful /api/features answer, for a viewer, without `pwa`. A
 * pending, failed or 401 answer, and the logged-out /login page, never touch the worker.
 */
export function usePwaLifecycle(): void {
  const { session } = useSession();
  const { visible, settled, on } = useFeature('pwa');
  const role = session?.role ?? null;
  useEffect(() => {
    if (visible) {
      linkManifest();
      void registerShell();
    } else if (settled && !on && role === 'viewer') {
      unlinkManifest();
      void removeShell();
    }
  }, [visible, settled, on, role]);
}
