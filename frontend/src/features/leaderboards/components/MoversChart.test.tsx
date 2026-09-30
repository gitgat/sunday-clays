import { screen, waitFor, within } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';

import { chartOptionIn, expectChartControls, expectExplainer } from '../../../test/charts';
import { LAZY_CHART } from '../../../test/lazyChart';
import { server } from '../../../test/msw/server';
import { renderWithProviders } from '../../../test/render';
import type { ClimberOut } from '../api';
import { moversFixture } from '../mocks';
import { MoversChart, moversModel } from './MoversChart';

const TITLE = 'Biggest rating gains';

function captureMovers(): URLSearchParams[] {
  const seen: URLSearchParams[] = [];
  server.use(
    http.get('*/api/leaderboards/movers', ({ request }) => {
      seen.push(new URL(request.url).searchParams);
      return HttpResponse.json(moversFixture);
    }),
  );
  return seen;
}

describe('moversModel', () => {
  it('one row per climber, biggest gain first as served, keeping the shooter id for highlights', () => {
    expect(moversModel(moversFixture.rows).rows).toEqual([
      { shooter_id: 9, display_name: 'Cy, Cal', gain: 3.4, n_rounds: 9 },
      { shooter_id: 3, display_name: 'Bee, Bob', gain: 1.2, n_rounds: 14 },
    ]);
  });

  it('has no rank or places column', () => {
    expect(moversModel(moversFixture.rows).columns.map((c) => c.key)).toEqual([
      'display_name',
      'gain',
      'n_rounds',
    ]);
  });

  it('tells apart two climbers with the same name', () => {
    const cal: ClimberOut = { shooter_id: 9, display_name: 'Cy, Cal', gain: 3.4, n_rounds: 9 };
    const names = moversModel([cal, { ...cal, shooter_id: 12, gain: 2 }]).rows.map(
      (r) => r.display_name,
    );
    expect(names).toEqual(['Cy, Cal #9', 'Cy, Cal #12']);
  });
});

describe('MoversChart', () => {
  it('shows the biggest gains with an explainer and chart controls, as of the time machine date', async () => {
    const seen = captureMovers();
    renderWithProviders(<MoversChart asOf="2026-09-13" />, { route: '/leaderboards' });
    const region = await screen.findByRole('region', { name: TITLE });
    await waitFor(() => within(region).getByRole('button', { name: 'Table' }), LAZY_CHART);
    expectChartControls(region);
    await expectExplainer(region, 'About this chart', { read: true });
    expect(region).toHaveTextContent('Rating points gained');
    expect(seen.at(-1)?.get('period')).toBe('season');
    expect(seen.at(-1)?.get('as_of')).toBe('2026-09-13');
    expect(seen.at(-1)?.has('since')).toBe(false);
  });

  it('follows a preset window that needs a start date', async () => {
    const seen = captureMovers();
    renderWithProviders(<MoversChart asOf={null} />, { route: '/leaderboards?w=3m' });
    await screen.findByRole('region', { name: TITLE });
    expect(seen.at(-1)?.get('since')).toBe('2026-06-28');
  });

  it('an All time window has no start date', async () => {
    server.use(
      http.get('*/api/leaderboards/movers', () =>
        HttpResponse.json({ ...moversFixture, period: 'all_time', start: null }),
      ),
    );
    renderWithProviders(<MoversChart asOf={null} />, { route: '/leaderboards?w=all' });
    const region = await screen.findByRole('region', { name: TITLE });
    expect(region).toHaveTextContent('Rating points gained, all time, to Sep 27, 2026');
  });

  it("an insight link's window and highlight set the dates and ring the shooter", async () => {
    const seen = captureMovers();
    renderWithProviders(<MoversChart asOf={null} />, {
      route: '/leaderboards?lb-movers.hl=s:9&lb-movers.from=2025-09-14&lb-movers.to=2026-09-13',
    });
    expect(await screen.findByText('Showing what the insight points to.')).toBeInTheDocument();
    await waitFor(() => expect(seen.at(-1)?.get('as_of')).toBe('2026-09-13'));
    expect(seen.at(-1)?.get('since')).toBe('2025-09-14');
  });

  it('passes the Members/Guests filter through', async () => {
    const seen = captureMovers();
    renderWithProviders(<MoversChart asOf={null} status="guest" />, { route: '/leaderboards' });
    await screen.findByRole('region', { name: TITLE });
    expect(seen.at(-1)?.get('status')).toBe('guest');
  });

  it('adds a highlighted climber outside the top ten to the inline chart', async () => {
    const rows = Array.from({ length: 12 }, (_, i) => ({
      shooter_id: i + 1,
      display_name: `Shooter ${String(i + 1)}`,
      gain: 12 - i,
      n_rounds: 9,
    }));
    server.use(
      http.get('*/api/leaderboards/movers', () => HttpResponse.json({ ...moversFixture, rows })),
    );
    renderWithProviders(<MoversChart asOf={null} />, {
      route: '/leaderboards?lb-movers.hl=s:12',
    });
    const region = await screen.findByRole('region', { name: TITLE });
    await waitFor(() => within(region).getByRole('button', { name: 'Table' }), LAZY_CHART);
    const axis = (chartOptionIn(region) as { yAxis: { data: string[] }[] }).yAxis;
    const names = axis[0]?.data ?? [];
    expect(names).toHaveLength(11);
    expect(names).toContain('Shooter 12');
  });

  it("names an insight link's dates, not the header window, when nobody gained", async () => {
    server.use(
      http.get('*/api/leaderboards/movers', () =>
        HttpResponse.json({ ...moversFixture, rows: [] }),
      ),
    );
    renderWithProviders(<MoversChart asOf={null} />, {
      route: '/leaderboards?lb-movers.from=2025-09-14&lb-movers.to=2026-09-13',
    });
    expect(
      await screen.findByText('No rating gains to show for Sep 14, 2025 – Sep 13, 2026 yet.'),
    ).toBeInTheDocument();
  });

  it('says so, kindly, when nobody has gained rating in the window', async () => {
    server.use(
      http.get('*/api/leaderboards/movers', () =>
        HttpResponse.json({ ...moversFixture, rows: [] }),
      ),
    );
    renderWithProviders(<MoversChart asOf={null} />, { route: '/leaderboards' });
    expect(
      await screen.findByText('No rating gains to show for the last 8 weeks yet.'),
    ).toBeInTheDocument();
  });

  it('says so when the request fails', async () => {
    server.use(http.get('*/api/leaderboards/movers', () => HttpResponse.json({}, { status: 500 })));
    renderWithProviders(<MoversChart asOf={null} />, { route: '/leaderboards' });
    expect(await screen.findByText('Couldn’t load the rating gains.')).toBeInTheDocument();
  });
});
