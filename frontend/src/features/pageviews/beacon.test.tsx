import { act, render, renderHook, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { createMemoryRouter, MemoryRouter, RouterProvider } from 'react-router';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { resetMeForTests, setMe, skipMe } from '../../lib/me';
import { meState, PAGE_VIEWS_PATH, sendPageView, usePageViewBeacon } from './beacon';

const DEVICE = '11111111-2222-4333-8444-555555555555';
const VIEW = {
  device_id: DEVICE,
  page_kind: 'home',
  me_state: 'none',
  at: '2026-10-01T18:00:00.000Z',
} as const;

afterEach(() => {
  // lib/me keeps an in-memory skip (fix/15-final): reset it so no state leaks between tests.
  resetMeForTests();
  localStorage.clear();
});

function at(path: string) {
  return ({ children }: { children: ReactNode }) => (
    <MemoryRouter initialEntries={[path]}>{children}</MemoryRouter>
  );
}

describe('meState', () => {
  it('is none, then skipped, then picked, and never a name', () => {
    expect(meState()).toBe('none');
    skipMe();
    expect(meState()).toBe('skipped');
    setMe(3);
    expect(meState()).toBe('picked');
  });
});

describe('sendPageView', () => {
  it('posts the JSON same-origin with keepalive and returns at once', () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockReturnValue(new Promise(() => undefined));
    expect(sendPageView(VIEW)).toBeUndefined(); // never awaited: the fetch never settles here
    expect(fetchSpy).toHaveBeenCalledWith(PAGE_VIEWS_PATH, {
      method: 'POST',
      keepalive: true,
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(VIEW),
    });
  });

  it('swallows a rejected fetch (offline, blocked)', async () => {
    // A plain function, not vi.fn/mockRejectedValue: those mark the rejection as handled.
    vi.stubGlobal('fetch', () => Promise.reject(new TypeError('Failed to fetch')));
    const unhandled = vi.fn();
    process.on('unhandledRejection', unhandled);
    try {
      sendPageView(VIEW);
      await new Promise((resolve) => setTimeout(resolve, 0));
      expect(unhandled).not.toHaveBeenCalled();
    } finally {
      process.off('unhandledRejection', unhandled);
      vi.unstubAllGlobals();
    }
  });

  it('swallows a fetch that throws synchronously', () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(() => {
      throw new TypeError('no fetch');
    });
    expect(() => sendPageView(VIEW)).not.toThrow();
  });
});

describe('usePageViewBeacon', () => {
  function spyFetch() {
    return vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(null, { status: 204 }));
  }

  it('sends the kind, the state and this browser’s device id for a viewer', async () => {
    localStorage.setItem('sc.device', DEVICE);
    const fetchSpy = spyFetch();
    renderHook(() => usePageViewBeacon('viewer'), { wrapper: at('/shooters/3?w=12m') });
    await waitFor(() => expect(fetchSpy).toHaveBeenCalledTimes(1));
    const body = JSON.parse(String(fetchSpy.mock.calls[0]?.[1]?.body)) as Record<string, string>;
    expect(Object.keys(body).sort()).toEqual(['at', 'device_id', 'me_state', 'page_kind']);
    expect(body).toMatchObject({ device_id: DEVICE, page_kind: 'profile', me_state: 'none' });
    expect(JSON.stringify(body)).not.toContain('shooters');
  });

  it('sends one beacon per pathname and none for a query-only change', async () => {
    // A synchronous fetch spy: each call is recorded the moment the effect runs, so an extra
    // beacon for `?w=12m` cannot arrive after the assertion (kills keying the effect on search).
    localStorage.setItem('sc.device', DEVICE);
    const fetchSpy = spyFetch();
    function Probe() {
      usePageViewBeacon('viewer');
      return null;
    }
    const router = createMemoryRouter([{ path: '*', element: <Probe /> }], {
      initialEntries: ['/shooters/3'],
    });
    render(<RouterProvider router={router} />);
    await act(() => router.navigate('/shooters/3?w=12m'));
    await act(() => router.navigate('/'));
    const kinds = fetchSpy.mock.calls.map(
      (call) => (JSON.parse(String(call[1]?.body)) as { page_kind: string }).page_kind,
    );
    expect(kinds).toEqual(['profile', 'home']);
  });

  it.each(['admin', null] as const)('sends nothing for the role %s', (role) => {
    const fetchSpy = spyFetch();
    renderHook(() => usePageViewBeacon(role), { wrapper: at('/') });
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it.each<[string, () => void]>([
    ['none', () => undefined],
    ['skipped', () => skipMe()],
    ['picked', () => setMe(3)],
  ])('reports me_state %s', async (state, arrange) => {
    localStorage.setItem('sc.device', DEVICE);
    arrange();
    const fetchSpy = spyFetch();
    renderHook(() => usePageViewBeacon('viewer'), { wrapper: at('/') });
    await waitFor(() => expect(fetchSpy).toHaveBeenCalledTimes(1));
    const body = JSON.parse(String(fetchSpy.mock.calls[0]?.[1]?.body)) as { me_state: string };
    expect(body.me_state).toBe(state);
  });

  it('sends nothing when the browser cannot keep a device id', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new DOMException('blocked', 'SecurityError');
    });
    const fetchSpy = spyFetch();
    renderHook(() => usePageViewBeacon('viewer'), { wrapper: at('/') });
    expect(fetchSpy).not.toHaveBeenCalled();
  });
});
