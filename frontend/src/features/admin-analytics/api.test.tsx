import { renderHook, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import type { ReactNode } from 'react';
import { MemoryRouter } from 'react-router';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { server } from '../../test/msw/server';
import { createTestQueryClient, renderWithProviders } from '../../test/render';
import { allTime, todayIso, useAnalyticsRange, useVisitors } from './api';
import { visitors } from './mocks';

afterEach(() => {
  vi.useRealTimers();
});

function at(path: string) {
  return ({ children }: { children: ReactNode }) => (
    <MemoryRouter initialEntries={[path]}>{children}</MemoryRouter>
  );
}

describe('analytics range', () => {
  it('is today in the browser’s calendar', () => {
    expect(todayIso(new Date(2026, 9, 1, 23, 59))).toBe('2026-10-01');
    expect(todayIso(new Date(2026, 0, 5, 0, 0))).toBe('2026-01-05');
  });

  it('follows the header window, anchored at today (default 8 weeks)', () => {
    vi.useFakeTimers({ toFake: ['Date'] });
    vi.setSystemTime(new Date(2026, 9, 1, 12, 0));
    const { result } = renderHook(() => useAnalyticsRange(), { wrapper: at('/admin/analytics') });
    expect(result.current.range).toEqual({ since: '2026-08-07', asOf: '2026-10-01' });
    expect(result.current.tag).toBe('Last 8 weeks · Aug 7 – Oct 1');
    const all = renderHook(() => useAnalyticsRange(), { wrapper: at('/admin/analytics?w=all') });
    expect(all.result.current.range).toEqual({ since: null, asOf: '2026-10-01' });
  });

  it('sends since and as_of, and leaves since out for all time', async () => {
    const seen: URLSearchParams[] = [];
    server.use(
      http.get('*/api/admin/analytics/visitors', ({ request }) => {
        seen.push(new URL(request.url).searchParams);
        return HttpResponse.json(visitors);
      }),
    );
    const queryClient = createTestQueryClient();
    function Probe({ all }: { all: boolean }) {
      useVisitors(all ? allTime('2026-10-01') : { since: '2026-08-07', asOf: '2026-10-01' });
      return null;
    }
    renderWithProviders(<Probe all={false} />, { queryClient });
    renderWithProviders(<Probe all />, { queryClient });
    await waitFor(() => expect(seen).toHaveLength(2));
    expect(seen.map((p) => [p.get('since'), p.get('as_of')])).toEqual(
      expect.arrayContaining([
        ['2026-08-07', '2026-10-01'],
        [null, '2026-10-01'],
      ]),
    );
  });
});
