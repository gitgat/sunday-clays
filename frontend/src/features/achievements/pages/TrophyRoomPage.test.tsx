import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { MemoryRouter, Route, Routes } from 'react-router';
import { describe, expect, it } from 'vitest';
import { expectChartControls, expectExplainer } from '../../../test/charts';
import { server } from '../../../test/msw/server';
import { achievementsFixture } from '../mocks';
import { TrophyRoomPage } from './TrophyRoomPage';

function renderAt(url: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[url]}>
        <Routes>
          <Route path="/achievements" element={<TrophyRoomPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('TrophyRoomPage', () => {
  it('lists every trophy with holders and rarity', async () => {
    renderAt('/achievements');
    expect(
      await screen.findByRole('heading', { level: 1, name: 'Trophy Room' }),
    ).toBeInTheDocument();
    const trophies = screen.getByRole('region', { name: 'Trophies' });
    expect(within(trophies).getAllByRole('listitem')).toHaveLength(3);
    expect(
      within(trophies).getByRole('link', {
        name: /Clays Broken.*1,000 clays broken.*65 holders · 19\.6%/,
      }),
    ).toHaveAttribute('href', '/achievements/clays_broken%3A3');
  });

  it('keeps the round-type filter on trophy and shooter links', async () => {
    renderAt('/achievements?rt=sporting');
    const trophies = await screen.findByRole('region', { name: 'Trophies' });
    expect(within(trophies).getByRole('link', { name: /First Win/ })).toHaveAttribute(
      'href',
      '/achievements/first_win?rt=sporting',
    );
    const recent = screen.getByRole('region', { name: 'Recent unlocks' });
    expect(within(recent).getByRole('link', { name: 'Hadley, Ike' })).toHaveAttribute(
      'href',
      '/shooters/12?rt=sporting',
    );
  });

  it('filters trophies by the category in the URL', async () => {
    renderAt('/achievements?cat=competition');
    const trophies = await screen.findByRole('region', { name: 'Trophies' });
    expect(within(trophies).getAllByRole('listitem')).toHaveLength(1);
    expect(within(trophies).getByRole('link', { name: /First Win/ })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Competition' })).toHaveAttribute(
      'aria-pressed',
      'true',
    );
  });

  it('switches category when a chip is pressed', async () => {
    const user = userEvent.setup();
    renderAt('/achievements');
    await user.click(await screen.findByRole('button', { name: 'Conditions' }));
    const conditions = screen.getByRole('region', { name: 'Trophies' });
    expect(within(conditions).getAllByRole('listitem')).toHaveLength(1);
    expect(within(conditions).getByRole('link', { name: /Rain Shooter/ })).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'All' }));
    expect(
      within(screen.getByRole('region', { name: 'Trophies' })).getAllByRole('listitem'),
    ).toHaveLength(3);
  });

  it('says "1 holder" for a single holder', async () => {
    const [first, ...rest] = achievementsFixture.trophies;
    if (!first) throw new Error('fixture has trophies');
    server.use(
      http.get('*/api/achievements', () =>
        HttpResponse.json({
          ...achievementsFixture,
          trophies: [{ ...first, holders: 1 }, ...rest],
        }),
      ),
    );
    renderAt('/achievements');
    const trophies = await screen.findByRole('region', { name: 'Trophies' });
    expect(within(trophies).getByText(/^1 holder ·/)).toBeInTheDocument();
  });

  it('links recent unlocks to shooter profiles', async () => {
    renderAt('/achievements');
    const recent = await screen.findByRole('region', { name: 'Recent unlocks' });
    expect(within(recent).getByRole('link', { name: 'Hadley, Ike' })).toHaveAttribute(
      'href',
      '/shooters/12',
    );
  });

  it('says so when nothing has been earned yet', async () => {
    server.use(
      http.get('*/api/achievements', () =>
        HttpResponse.json({ ...achievementsFixture, recent: [] }),
      ),
    );
    renderAt('/achievements');
    expect(await screen.findByText('No trophies have been earned yet.')).toBeInTheDocument();
  });

  it('exposes Table and CSV controls on every chart', async () => {
    renderAt('/achievements');
    await screen.findByRole('heading', { level: 1, name: 'Trophy Room' });
    expectChartControls(screen.getByRole('region', { name: 'Rarity' }));
    expect(screen.getAllByRole('button', { name: /table/i })).toHaveLength(1);
    await expectExplainer(screen.getByRole('region', { name: 'Rarity' }), undefined, {
      read: true,
    });
  });

  it('shows an error when the API fails', async () => {
    server.use(http.get('*/api/achievements', () => new HttpResponse(null, { status: 500 })));
    renderAt('/achievements');
    expect(await screen.findByRole('alert')).toHaveTextContent('Could not load the Trophy Room.');
  });

  it('shows dates as Sep 13, 2026, not ISO', async () => {
    renderAt('/achievements');
    const recent = await screen.findByRole('region', { name: 'Recent unlocks' });
    expect(within(recent).getByText('Sep 13, 2026')).toHaveAttribute('datetime', '2026-09-13');
  });

  it('shows 10 recent unlocks, then every one after "Show all N"', async () => {
    const [first] = achievementsFixture.recent;
    if (!first) throw new Error('fixture has a recent unlock');
    const recent = Array.from({ length: 24 }, (_, i) => ({ ...first, shooter_id: 100 + i }));
    server.use(
      http.get('*/api/achievements', () =>
        HttpResponse.json({ ...achievementsFixture, recent, recent_total: 24 }),
      ),
    );
    const user = userEvent.setup();
    renderAt('/achievements');
    const region = await screen.findByRole('region', { name: 'Recent unlocks' });
    expect(within(region).getAllByRole('listitem')).toHaveLength(10);
    await user.click(within(region).getByRole('button', { name: 'Show all 24 unlocks' }));
    expect(within(region).getAllByRole('listitem')).toHaveLength(24);
    expect(within(region).queryByRole('button', { name: /Show all/ })).not.toBeInTheDocument();
    expect(within(region).queryByText(/Showing the latest/)).not.toBeInTheDocument();
  });

  it('offers no "Show all" for 10 or fewer unlocks', async () => {
    renderAt('/achievements');
    const region = await screen.findByRole('region', { name: 'Recent unlocks' });
    expect(within(region).queryByRole('button', { name: /Show all/ })).not.toBeInTheDocument();
  });

  it('offers the latest capped list, then says how many of the total it holds', async () => {
    const [first] = achievementsFixture.recent;
    if (!first) throw new Error('fixture has a recent unlock');
    const recent = Array.from({ length: 24 }, (_, i) => ({ ...first, shooter_id: 100 + i }));
    server.use(
      http.get('*/api/achievements', () =>
        HttpResponse.json({ ...achievementsFixture, recent, recent_total: 3412 }),
      ),
    );
    const user = userEvent.setup();
    renderAt('/achievements');
    const region = await screen.findByRole('region', { name: 'Recent unlocks' });
    expect(within(region).queryByText(/of 3,412/)).not.toBeInTheDocument();
    expect(within(region).queryByRole('button', { name: /Show all/ })).not.toBeInTheDocument();
    await user.click(within(region).getByRole('button', { name: 'Show the latest 24 unlocks' }));
    expect(within(region).getAllByRole('listitem')).toHaveLength(24);
    expect(within(region).getByText('The latest 24 of 3,412 unlocks are listed.')).toBeVisible();
  });

  it('says how many of the total a short capped list holds', async () => {
    server.use(
      http.get('*/api/achievements', () =>
        HttpResponse.json({ ...achievementsFixture, recent_total: 950 }),
      ),
    );
    renderAt('/achievements');
    expect(await screen.findByText('The latest 1 of 950 unlocks are listed.')).toBeInTheDocument();
  });
});
