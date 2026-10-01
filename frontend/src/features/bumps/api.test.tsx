import { QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import type { ReactNode } from 'react';
import { describe, expect, it } from 'vitest';
import { server } from '../../test/msw/server';
import { createTestQueryClient } from '../../test/render';
import { BATCH, sortedKeys, toggled, useBumps } from './api';

const DEVICE = '00000000-0000-4000-8000-00000000000a';

function wrapper({ children }: { children: ReactNode }) {
  return <QueryClientProvider client={createTestQueryClient()}>{children}</QueryClientProvider>;
}

describe('toggled', () => {
  it('adds and takes back this device’s bump', () => {
    const start = { k: { bumps: 2, bumped: false } };
    expect(toggled(start, 'k', true)).toEqual({ k: { bumps: 3, bumped: true } });
    expect(toggled({ k: { bumps: 3, bumped: true } }, 'k', false)).toEqual({
      k: { bumps: 2, bumped: false },
    });
  });

  it('is a no-op when the state already matches, and never goes below zero', () => {
    expect(toggled({ k: { bumps: 3, bumped: true } }, 'k', true)).toEqual({
      k: { bumps: 3, bumped: true },
    });
    expect(toggled({ k: { bumps: 0, bumped: true } }, 'k', false)).toEqual({
      k: { bumps: 0, bumped: false },
    });
  });

  it('starts an insight nobody bumped at zero and keeps the others', () => {
    expect(toggled(undefined, 'k', true)).toEqual({ k: { bumps: 1, bumped: true } });
    expect(toggled({ j: { bumps: 4, bumped: false } }, 'k', true)).toEqual({
      j: { bumps: 4, bumped: false },
      k: { bumps: 1, bumped: true },
    });
  });
});

describe('sortedKeys', () => {
  it('drops repeats and sorts, so one set is one query', () => {
    expect(sortedKeys(['b', 'a', 'b'])).toEqual(['a', 'b']);
  });
});

describe('useBumps', () => {
  it('asks once for every key, with this device', async () => {
    const asked: URLSearchParams[] = [];
    server.use(
      http.get('*/api/bumps', ({ request }) => {
        asked.push(new URL(request.url).searchParams);
        return HttpResponse.json({ a: { bumps: 2, bumped: true }, b: { bumps: 0, bumped: false } });
      }),
    );
    const { result } = renderHook(() => useBumps(['a', 'b'], DEVICE), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual({
      a: { bumps: 2, bumped: true },
      b: { bumps: 0, bumped: false },
    });
    expect(asked).toHaveLength(1);
    expect(asked[0]?.get('keys')).toBe('a,b');
    expect(asked[0]?.get('device_id')).toBe(DEVICE);
  });

  it('sends no device id when this browser has none', async () => {
    const asked: URLSearchParams[] = [];
    server.use(
      http.get('*/api/bumps', ({ request }) => {
        asked.push(new URL(request.url).searchParams);
        return HttpResponse.json({});
      }),
    );
    const { result } = renderHook(() => useBumps(['a'], null), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(asked[0]?.has('device_id')).toBe(false);
  });

  it('asks nothing for no keys', () => {
    const { result } = renderHook(() => useBumps([], DEVICE), { wrapper });
    expect(result.current.fetchStatus).toBe('idle');
  });

  it('splits more than 100 keys into parallel asks and merges the answers', async () => {
    const sizes: number[] = [];
    server.use(
      http.get('*/api/bumps', ({ request }) => {
        const keys = (new URL(request.url).searchParams.get('keys') ?? '').split(',');
        sizes.push(keys.length);
        return HttpResponse.json(
          Object.fromEntries(keys.map((k) => [k, { bumps: 1, bumped: false }])),
        );
      }),
    );
    const keys = Array.from({ length: BATCH + 50 }, (_, i) => `k${String(i).padStart(3, '0')}`);
    const { result } = renderHook(() => useBumps(keys, DEVICE), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(sizes.sort((x, y) => y - x)).toEqual([100, 50]);
    expect(Object.keys(result.current.data ?? {})).toHaveLength(150);
  });
});
