import { screen, waitFor } from '@testing-library/react';
import { http, HttpResponse, type JsonBodyType } from 'msw';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { LAZY_CHART, LAZY_TEST_TIMEOUT } from '../../../test/lazyChart';
import { server } from '../../../test/msw/server';
import { renderWithProviders } from '../../../test/render';
import { bumps, pageKinds, uptake, visitors } from '../mocks';
import { AnalyticsPage } from './AnalyticsPage';

afterEach(() => {
  vi.useRealTimers();
});

describe('AnalyticsPage', () => {
  it(
    'shows the window once and the four charts',
    async () => {
      vi.useFakeTimers({ toFake: ['Date'] });
      vi.setSystemTime(new Date(2026, 9, 1, 12, 0));
      renderWithProviders(<AnalyticsPage />, { route: '/admin/analytics' });
      expect(screen.getByRole('heading', { level: 1, name: 'Analytics' })).toBeInTheDocument();
      expect(screen.getByText(/^Last 8 weeks · Aug 7 – Oct 1\./)).toBeInTheDocument();
      for (const name of [
        'Visitors',
        'Busiest days',
        'Page views by page',
        'Fist bumps per day',
        'Most-bumped insights',
        '“Which one are you?” answers',
      ]) {
        expect(await screen.findByRole('region', { name }, LAZY_CHART)).toBeInTheDocument();
      }
    },
    LAZY_TEST_TIMEOUT,
  );

  it.each([
    ['/admin/analytics', '2026-08-07'],
    ['/admin/analytics?w=12m', '2025-10-02'],
  ])(
    'sends the header window to all four endpoints (%s)',
    async (route, start) => {
      vi.useFakeTimers({ toFake: ['Date'] });
      vi.setSystemTime(new Date(2026, 9, 1, 12, 0));
      const seen = new Map<string, string[]>();
      const record = (name: string, body: JsonBodyType) =>
        http.get(`*/api/admin/analytics/${name}`, ({ request }) => {
          const q = new URL(request.url).searchParams;
          seen.set(name, [
            ...(seen.get(name) ?? []),
            `${String(q.get('since'))}|${String(q.get('as_of'))}`,
          ]);
          return HttpResponse.json(body);
        });
      server.use(
        record('visitors', visitors),
        record('pages', pageKinds),
        record('bumps', bumps),
        record('me-states', uptake),
      );
      renderWithProviders(<AnalyticsPage />, { route });
      await waitFor(() => expect(seen.size).toBe(4), LAZY_CHART);
      for (const name of ['visitors', 'pages', 'bumps', 'me-states']) {
        expect(seen.get(name), name).toEqual([`${start}|2026-10-01`]);
      }
    },
    LAZY_TEST_TIMEOUT,
  );
});
