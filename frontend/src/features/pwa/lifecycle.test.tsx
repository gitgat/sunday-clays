import { renderHook, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import type { ReactNode } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { AppProviders } from '../../app/providers';
import { SESSION_QUERY_KEY, type Role } from '../auth/api';
import { server } from '../../test/msw/server';
import { createTestQueryClient } from '../../test/render';
import { MANIFEST_HREF, usePwaLifecycle } from './lifecycle';

const register = vi.fn().mockResolvedValue({});
const unregister = vi.fn().mockResolvedValue(true);
const getRegistrations = vi.fn().mockResolvedValue([{ unregister }]);
const cacheKeys = vi.fn().mockResolvedValue(['sc-shell-aaa', 'other-cache']);
const cacheDelete = vi.fn().mockResolvedValue(true);

beforeEach(() => {
  vi.stubGlobal('navigator', { ...navigator, serviceWorker: { register, getRegistrations } });
  vi.stubGlobal('caches', { keys: cacheKeys, delete: cacheDelete });
});
afterEach(() => {
  document.querySelectorAll('link[rel="manifest"]').forEach((el) => el.remove());
  vi.clearAllMocks();
});

function wrapper(role: Role | null) {
  const queryClient = createTestQueryClient();
  queryClient.setQueryData(SESSION_QUERY_KEY, role === null ? null : { role });
  return ({ children }: { children: ReactNode }) => (
    <AppProviders queryClient={queryClient}>{children}</AppProviders>
  );
}

const switches = (on: boolean) =>
  server.use(
    http.get('*/api/features', () => HttpResponse.json({ switches: on ? { pwa: true } : {} })),
  );

const settle = () => new Promise((resolve) => setTimeout(resolve, 50));

describe('usePwaLifecycle', () => {
  it('links the manifest and registers the worker while visible', async () => {
    switches(true);
    renderHook(() => usePwaLifecycle(), { wrapper: wrapper('viewer') });
    await waitFor(() => expect(register).toHaveBeenCalledWith('/sw.js', { scope: '/' }));
    expect(document.querySelector(`link[rel="manifest"][href="${MANIFEST_HREF}"]`)).not.toBeNull();
  });

  it('unregisters and deletes shell caches on a definite off for a viewer', async () => {
    switches(false);
    renderHook(() => usePwaLifecycle(), { wrapper: wrapper('viewer') });
    await waitFor(() => expect(unregister).toHaveBeenCalled());
    await waitFor(() => expect(cacheDelete).toHaveBeenCalledWith('sc-shell-aaa'));
    expect(cacheDelete).not.toHaveBeenCalledWith('other-cache');
    expect(register).not.toHaveBeenCalled();
  });

  it('links the manifest only once', async () => {
    switches(true);
    renderHook(() => usePwaLifecycle(), { wrapper: wrapper('viewer') });
    renderHook(() => usePwaLifecycle(), { wrapper: wrapper('viewer') });
    await waitFor(() => expect(register).toHaveBeenCalledTimes(2));
    expect(document.querySelectorAll('link[rel="manifest"]')).toHaveLength(1);
  });

  it('unlinks the manifest on a definite off for a viewer', async () => {
    const link = document.createElement('link');
    link.rel = 'manifest';
    link.href = MANIFEST_HREF;
    document.head.appendChild(link);
    switches(false);
    renderHook(() => usePwaLifecycle(), { wrapper: wrapper('viewer') });
    await waitFor(() => expect(document.querySelector('link[rel="manifest"]')).toBeNull());
  });

  it('swallows a failure while removing the shell', async () => {
    getRegistrations.mockRejectedValueOnce(new Error('boom'));
    const unhandled = vi.fn();
    process.on('unhandledRejection', unhandled);
    switches(false);
    renderHook(() => usePwaLifecycle(), { wrapper: wrapper('viewer') });
    await waitFor(() => expect(getRegistrations).toHaveBeenCalled());
    await settle();
    process.off('unhandledRejection', unhandled);
    expect(unhandled).not.toHaveBeenCalled();
  });

  it('does nothing where service workers and caches do not exist', async () => {
    const bare: Record<string, unknown> = { ...navigator };
    delete bare.serviceWorker;
    vi.stubGlobal('navigator', bare);
    delete (window as unknown as Record<string, unknown>).caches;
    switches(true);
    renderHook(() => usePwaLifecycle(), { wrapper: wrapper('viewer') });
    await settle();
    expect(register).not.toHaveBeenCalled();
    switches(false);
    renderHook(() => usePwaLifecycle(), { wrapper: wrapper('viewer') });
    await settle();
    expect(getRegistrations).not.toHaveBeenCalled();
  });

  it('leaves the registration alone while pending', async () => {
    server.use(http.get('*/api/features', () => new Promise(() => undefined)));
    renderHook(() => usePwaLifecycle(), { wrapper: wrapper('viewer') });
    await settle();
    expect(getRegistrations).not.toHaveBeenCalled();
    expect(cacheDelete).not.toHaveBeenCalled();
  });

  it('leaves the registration alone after a network error', async () => {
    server.use(http.get('*/api/features', () => HttpResponse.error()));
    renderHook(() => usePwaLifecycle(), { wrapper: wrapper('viewer') });
    await settle();
    expect(getRegistrations).not.toHaveBeenCalled();
  });

  it('leaves the registration alone after a 401', async () => {
    server.use(
      http.get('*/api/features', () =>
        HttpResponse.json({ error: { code: 'unauthenticated', message: 'x' } }, { status: 401 }),
      ),
    );
    renderHook(() => usePwaLifecycle(), { wrapper: wrapper('viewer') });
    await settle();
    expect(getRegistrations).not.toHaveBeenCalled();
  });

  it('leaves the registration alone on /login (no session, no request)', async () => {
    switches(false);
    renderHook(() => usePwaLifecycle(), { wrapper: wrapper(null) });
    await settle();
    expect(getRegistrations).not.toHaveBeenCalled();
    expect(register).not.toHaveBeenCalled();
  });

  it('registers for an admin previewing it, and never unregisters for an admin', async () => {
    switches(false);
    renderHook(() => usePwaLifecycle(), { wrapper: wrapper('admin') });
    await waitFor(() => expect(register).toHaveBeenCalled());
    expect(getRegistrations).not.toHaveBeenCalled();
  });
});
