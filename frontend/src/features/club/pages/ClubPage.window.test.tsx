import type { EChartsOption } from 'echarts';
import { screen, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { QuerySpec } from '../../../components/charts/explore';
import { server } from '../../../test/msw/server';
import { renderWithProviders } from '../../../test/render';
import { LAZY_CHART, LAZY_TEST_TIMEOUT } from '../../../test/lazyChart';

// A stand-in chart that records the option each chart is drawn with, so the initial zoom is visible.
const drawn = vi.hoisted(() => new Map<string, EChartsOption>());
vi.mock('../../../components/charts/EChart', () => ({
  EChart: ({ option, ariaLabel }: { option: EChartsOption; ariaLabel: string }) => {
    drawn.set(ariaLabel, option);
    return <div role="img" aria-label={ariaLabel} />;
  },
}));

const { ClubPage } = await import('./ClubPage');

const zoom = (title: string) =>
  [drawn.get(`${title} chart`)?.dataZoom ?? []].flat().find((z) => z.type === 'inside') as
    { startValue?: string | number; endValue?: string | number } | undefined;

describe('ClubPage time window', { timeout: LAZY_TEST_TIMEOUT }, () => {
  const specs: QuerySpec[] = [];

  beforeEach(() => {
    drawn.clear();
    specs.length = 0;
    server.use(
      http.post('*/api/explore', async ({ request }) => {
        specs.push((await request.json()) as QuerySpec);
        return HttpResponse.json({
          columns: [
            { key: 'condition', label: 'Conditions', type: 'string' },
            { key: 'value', label: 'Attendance (avg)', type: 'number' },
          ],
          rows: [{ condition: 'clear', value: 24 }],
          n_rounds: 0,
          truncated: false,
        });
      }),
    );
  });

  it('opens the time series zoomed to the last 8 weeks, from the latest scored Sunday', async () => {
    renderWithProviders(<ClubPage />, { route: '/club' });
    await waitFor(() => expect(zoom('Attendance per Sunday')).toBeDefined(), LAZY_CHART);
    // The mock's latest scored Sunday is 2026-09-27; 8 weeks back is 2026-08-03.
    expect(zoom('Attendance per Sunday')).toMatchObject({ startValue: '2026-08-03' });
    await waitFor(() => expect(zoom('Median and top score')).toBeDefined(), LAZY_CHART);
    expect(zoom('Median and top score')).toMatchObject({ startValue: '2026-08-03' });
    await waitFor(() => expect(zoom('Difficulty by Sunday')).toBeDefined(), LAZY_CHART);
    // The per-year charts are not time series on a date axis: they ignore the window.
    expect(zoom('Shooters and Sundays per year')?.startValue).toBeUndefined();
  });

  it('runs the turnout query once, for the Sundays inside the window', async () => {
    renderWithProviders(<ClubPage />, { route: '/club' });
    await waitFor(() => expect(specs.length).toBeGreaterThan(0), LAZY_CHART);
    expect(specs).toHaveLength(1);
    expect(specs[0]?.filters).toMatchObject({ date_from: '2026-08-03', date_to: '2026-09-27' });
  });

  it('shows the whole history with All time', async () => {
    renderWithProviders(<ClubPage />, { route: '/club?w=all' });
    await waitFor(() => expect(specs.length).toBeGreaterThan(0), LAZY_CHART);
    expect(specs[0]?.filters).toMatchObject({ date_from: null, date_to: '2026-09-27' });
    await waitFor(() => expect(drawn.has('Attendance per Sunday chart')).toBe(true), LAZY_CHART);
    expect(zoom('Attendance per Sunday')?.startValue).toBeUndefined();
  });

  it('runs the turnout query without a window when nothing is scored yet', async () => {
    server.use(http.get('*/api/meta', () => HttpResponse.json({ last_score_date: null })));
    renderWithProviders(<ClubPage />, { route: '/club' });
    await waitFor(() => expect(specs.length).toBeGreaterThan(0), LAZY_CHART);
    expect(specs[0]?.filters).toMatchObject({ date_from: null, date_to: null });
    expect(screen.getByRole('heading', { level: 1, name: 'Club' })).toBeInTheDocument();
  });
});
