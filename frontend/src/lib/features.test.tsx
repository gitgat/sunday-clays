import { act, renderHook, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import type { ReactNode } from 'react';
import { describe, expect, it } from 'vitest';
import { AppProviders } from '../app/providers';
import { SESSION_QUERY_KEY, type Role } from '../features/auth/api';
import { server } from '../test/msw/server';
import { createTestQueryClient } from '../test/render';
import { FEATURES_QUERY_KEY, featureState, useFeature } from './features';

describe('featureState', () => {
  it('takes launch-switch keys only, never the page-cache kill switch', () => {
    // @ts-expect-error page_cache is infrastructure: an admin would otherwise "preview" it
    expect(featureState({}, 'viewer', 'page_cache').visible).toBe(false);
  });

  it.each<[Role, boolean, { visible: boolean; preview: boolean; on: boolean }]>([
    ['viewer', true, { visible: true, preview: false, on: true }],
    ['viewer', false, { visible: false, preview: false, on: false }],
    ['admin', true, { visible: true, preview: false, on: true }],
    ['admin', false, { visible: true, preview: true, on: false }],
  ])('%s with the switch %s', (role, on, expected) => {
    const switches: Record<string, boolean> = on ? { pwa: true } : {};
    expect(featureState(switches, role, 'pwa')).toEqual({ ...expected, settled: true });
  });

  it('is invisible and unsettled before the switches are known, even for an admin', () => {
    expect(featureState(undefined, 'admin', 'pwa')).toEqual({
      visible: false,
      preview: false,
      on: false,
      settled: false,
    });
  });

  it('reads a missing key as off', () => {
    expect(featureState({ tour_glossary: true }, 'viewer', 'pwa').on).toBe(false);
  });
});

function wrapperFor(role: Role | null, queryClient = createTestQueryClient()) {
  queryClient.setQueryData(SESSION_QUERY_KEY, role === null ? null : { role });
  return ({ children }: { children: ReactNode }) => (
    <AppProviders queryClient={queryClient}>{children}</AppProviders>
  );
}

describe('useFeature', () => {
  it('turns visible once /api/features answers', async () => {
    server.use(http.get('*/api/features', () => HttpResponse.json({ switches: { pwa: true } })));
    const { result } = renderHook(() => useFeature('pwa'), { wrapper: wrapperFor('viewer') });
    expect(result.current.visible).toBe(false); // pending: nothing flashes in
    await waitFor(() => expect(result.current.settled).toBe(true));
    expect(result.current).toEqual({ visible: true, preview: false, on: true, settled: true });
  });

  it('never asks without a session (the login page)', async () => {
    let asked = 0;
    server.use(
      http.get('*/api/features', () => {
        asked += 1;
        return HttpResponse.json({ switches: {} });
      }),
    );
    const { result } = renderHook(() => useFeature('pwa'), { wrapper: wrapperFor(null) });
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(asked).toBe(0);
    expect(result.current.settled).toBe(false);
  });

  it('stays unsettled after a failed request', async () => {
    server.use(http.get('*/api/features', () => HttpResponse.error()));
    const { result } = renderHook(() => useFeature('pwa'), { wrapper: wrapperFor('admin') });
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(result.current).toEqual({ visible: false, preview: false, on: false, settled: false });
  });

  it('stays unsettled after a 401', async () => {
    server.use(
      http.get('*/api/features', () =>
        HttpResponse.json(
          { error: { code: 'unauthenticated', message: 'Log in' } },
          { status: 401 },
        ),
      ),
    );
    const { result } = renderHook(() => useFeature('pwa'), { wrapper: wrapperFor('viewer') });
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(result.current).toEqual({ visible: false, preview: false, on: false, settled: false });
  });

  it('keeps the last known switches when a later refetch fails', async () => {
    server.use(http.get('*/api/features', () => HttpResponse.json({ switches: { pwa: true } })));
    const queryClient = createTestQueryClient();
    const { result } = renderHook(() => useFeature('pwa'), {
      wrapper: wrapperFor('viewer', queryClient),
    });
    await waitFor(() => expect(result.current.settled).toBe(true));
    server.use(http.get('*/api/features', () => HttpResponse.error()));
    await act(() => queryClient.refetchQueries({ queryKey: FEATURES_QUERY_KEY }));
    expect(queryClient.getQueryState(FEATURES_QUERY_KEY)?.status).toBe('error');
    await new Promise((resolve) => setTimeout(resolve, 50)); // let the error reach the hook
    expect(result.current).toEqual({ visible: true, preview: false, on: true, settled: true });
  });
});
