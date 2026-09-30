import { screen, within } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { Route, Routes } from 'react-router';
import { describe, expect, it } from 'vitest';
import { expectChartControls, expectExplainer } from '../../../test/charts';
import { LAZY_CHART, LAZY_TEST_TIMEOUT } from '../../../test/lazyChart';
import { server } from '../../../test/msw/server';
import { renderWithProviders } from '../../../test/render';
import { YIR_GRIMSBY_2025 } from '../mocks';
import { YirShooterPage } from './YirShooterPage';

function renderShooter(body: unknown, status = 200) {
  server.use(
    http.get('*/api/yir/:year/shooters/:id', () =>
      HttpResponse.json(body as Record<string, unknown>, { status }),
    ),
  );
  return renderWithProviders(
    <Routes>
      <Route path="/yir/:year/shooters/:id" element={<YirShooterPage />} />
    </Routes>,
    { route: '/yir/2025/shooters/307' },
  );
}

describe('YirShooterPage', () => {
  it("summarises the shooter's year", async () => {
    renderShooter(YIR_GRIMSBY_2025);
    const year = await screen.findByRole('region', { name: 'Grimsby, Gregor: 2025' });
    expect(within(year).getByText('26 (+3 vs 2024)')).toBeInTheDocument();
    expect(within(year).getByText('43.30 (+1.30 vs 2024)')).toBeInTheDocument();
    expect(within(year).getByText('19th of 139')).toBeInTheDocument();
    expect(within(year).getByText('44.10 → 45.32')).toBeInTheDocument();
    expect(within(year).getByText('Rating gain')).toBeInTheDocument();
    const best = screen.getByRole('region', { name: 'Grimsby, Gregor: best of 2025' });
    expect(within(best).getByText('50 on Aug 3')).toBeInTheDocument();
    expect(within(best).getByText('1st')).toBeInTheDocument();
    expect(within(best).getByText('49 (Mar 23), 50 (Aug 3)')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: "Back to the club's 2025" })).toHaveAttribute(
      'href',
      '/yir/2025',
    );
  });

  it(
    'every data chart exposes Table and CSV controls and an explainer',
    async () => {
      renderShooter(YIR_GRIMSBY_2025);
      const chart = await screen.findByRole('region', { name: 'Month by month' }, LAZY_CHART);
      expectChartControls(chart);
      await expectExplainer(chart, 'About this chart', { read: true });
    },
    LAZY_TEST_TIMEOUT,
  );

  it('explains each card in plain language', async () => {
    renderShooter(YIR_GRIMSBY_2025);
    await expectExplainer(
      await screen.findByRole('region', { name: 'Grimsby, Gregor: 2025' }),
      'About this card',
    );
    await expectExplainer(
      screen.getByRole('region', { name: 'Grimsby, Gregor: best of 2025' }),
      'About this card',
    );
  });

  it('only celebrates gains: a dip is not shown and neither is a lower rating', async () => {
    renderShooter({
      ...YIR_GRIMSBY_2025,
      rating_start: 46,
      rating_end: 45,
      totals: { ...YIR_GRIMSBY_2025.totals, events: 20, rounds: 20, avg_score: 40 },
    });
    const year = await screen.findByRole('region', { name: 'Grimsby, Gregor: 2025' });
    expect(within(year).getAllByText('20')).toHaveLength(2);
    expect(within(year).getByText('40.00')).toBeInTheDocument();
    expect(year).not.toHaveTextContent('vs 2024)');
    expect(year).not.toHaveTextContent('→');
  });

  it('handles a year without rounds', async () => {
    renderShooter({
      ...YIR_GRIMSBY_2025,
      totals: {
        ...YIR_GRIMSBY_2025.totals,
        events: 0,
        rounds: 0,
        clays_thrown: 0,
        clays_broken: 0,
        avg_score: null,
      },
      best: null,
      wins: 0,
      podiums: 0,
      best_finish: null,
      pbs: [],
      trophies: 0,
      rating_start: null,
      rating_end: null,
      attendance_rank: null,
      previous: null,
    });
    expect(await screen.findByText('No rounds in 2025.')).toBeInTheDocument();
    expect(screen.getByText('None this year')).toBeInTheDocument();
    expect(screen.getAllByText('—').length).toBeGreaterThanOrEqual(4);
  });

  it('sends the round-type filter (C10)', async () => {
    const roundTypes: string[][] = [];
    server.use(
      http.get('*/api/yir/:year/shooters/:id', ({ request }) => {
        roundTypes.push(new URL(request.url).searchParams.getAll('round_type'));
        return HttpResponse.json(YIR_GRIMSBY_2025);
      }),
    );
    renderWithProviders(
      <Routes>
        <Route path="/yir/:year/shooters/:id" element={<YirShooterPage />} />
      </Routes>,
      { route: '/yir/2025/shooters/307?rt=sporting' },
    );
    await screen.findByRole('region', { name: 'Grimsby, Gregor: 2025' });
    expect(roundTypes).toEqual([['sporting']]);
  });

  it('shows the server message for an unknown shooter', async () => {
    renderShooter(
      { error: { code: 'shooter_not_found', message: 'No shooter with id 307.' } },
      404,
    );
    expect(await screen.findByRole('alert')).toHaveTextContent('No shooter with id 307.');
  });
});
