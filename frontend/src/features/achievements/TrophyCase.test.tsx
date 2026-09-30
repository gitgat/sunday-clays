import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, within } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { MemoryRouter } from 'react-router';
import { describe, expect, it } from 'vitest';
import { expectChartControls, expectExplainer } from '../../test/charts';
import { server } from '../../test/msw/server';
import { shooterAchievementsFixture } from './mocks';
import { TrophyCase, trophyDates } from './TrophyCase';

function renderCase() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <TrophyCase shooterId={12} />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('TrophyCase', () => {
  it('shows earned trophies with repeat counts', async () => {
    renderCase();
    const region = await screen.findByRole('region', { name: 'Trophy case for this shooter' });
    expect(within(region).getByText('Welcome Back ×2')).toBeInTheDocument();
    expect(within(region).getByText('100 clays broken')).toBeInTheDocument();
  });

  it('tags the earned trophies as lifetime and the timeline as all years', async () => {
    renderCase();
    const region = await screen.findByRole('region', { name: 'Trophy case for this shooter' });
    expect(within(region).getByText('Lifetime')).toBeVisible();
    expect(within(region).getByText('Trophies earned over time · all years')).toBeVisible();
  });

  it('shows progress toward each next tier', async () => {
    renderCase();
    expect(await screen.findByText('1,742 / 2,500 clays broken')).toBeInTheDocument();
    expect(screen.getByRole('progressbar', { name: 'Clays Broken progress' })).toHaveAttribute(
      'aria-valuenow',
      '1742',
    );
    expect(screen.getByText('All tiers earned')).toBeInTheDocument();
  });

  it('greys out locked one-off trophies', async () => {
    renderCase();
    expect(await screen.findByText('Mudder')).toBeInTheDocument();
    expect(screen.getByText('Broke 40 or more in the rain.')).toBeInTheDocument();
  });

  it('exposes Table and CSV controls on every chart', async () => {
    renderCase();
    await screen.findByRole('region', { name: 'Trophy case for this shooter' });
    expectChartControls(screen.getByRole('region', { name: 'Trophy timeline' }));
    expect(screen.getAllByRole('button', { name: /table/i })).toHaveLength(1);
  });

  it('explains the timeline chart and the next tiers', async () => {
    renderCase();
    const region = await screen.findByRole('region', { name: 'Trophy case for this shooter' });
    await expectExplainer(
      within(region).getByRole('region', { name: 'Trophy timeline' }),
      undefined,
      {
        read: true,
      },
    );
    await expectExplainer(region, 'About next tiers');
    expect(within(region).getAllByText('All time')).toHaveLength(2);
  });

  it('hides the empty Locked block and timeline for a shooter with nothing yet', async () => {
    server.use(
      http.get('*/api/shooters/:id/achievements', () =>
        HttpResponse.json({ ...shooterAchievementsFixture, earned: [], locked: [] }),
      ),
    );
    renderCase();
    expect(await screen.findByText(/No trophies yet/)).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Locked' })).not.toBeInTheDocument();
    expect(screen.queryByRole('region', { name: 'Trophy timeline' })).not.toBeInTheDocument();
  });

  it('encourages a shooter without trophies', async () => {
    server.use(
      http.get('*/api/shooters/:id/achievements', () =>
        HttpResponse.json({ ...shooterAchievementsFixture, earned: [] }),
      ),
    );
    renderCase();
    expect(await screen.findByText(/No trophies yet/)).toBeInTheDocument();
  });

  it('shows an error when the API fails', async () => {
    server.use(
      http.get('*/api/shooters/:id/achievements', () => new HttpResponse(null, { status: 500 })),
    );
    renderCase();
    expect(await screen.findByRole('alert')).toBeInTheDocument();
  });

  it('shows earned dates as Apr 2, 2023, not ISO', async () => {
    renderCase();
    const region = await screen.findByRole('region', { name: 'Trophy case for this shooter' });
    expect(within(region).getByText('Apr 2, 2023')).toHaveAttribute('datetime', '2023-04-02');
  });
});

describe('trophyDates', () => {
  it("maps an insight's trophy codes to the dates they were earned", () => {
    const rows = [
      { date: '2026-03-01', trophy: 'Ironman', code: 'ironman' },
      { date: '2026-05-03', trophy: 'Cold snap', code: 'cold' },
      { date: '2026-06-07', trophy: 'Ironman', code: 'ironman' },
    ];
    expect(trophyDates(['ironman'], rows)).toEqual(['2026-03-01', '2026-06-07']);
    expect(trophyDates(['none'], rows)).toEqual([]);
  });
});
